from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from job_digest.models import JobRecord, JobState, PacketJob, RunStats, ScoreResult


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.connection.close()

    def _init_schema(self) -> None:
        with closing(self.connection.cursor()) as cursor:
            cursor.executescript(
                """
                PRAGMA journal_mode=DELETE;
                CREATE TABLE IF NOT EXISTS jobs (
                    identity TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    source_job_id TEXT,
                    canonical_url TEXT NOT NULL,
                    apply_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    raw_location TEXT NOT NULL,
                    normalized_location TEXT NOT NULL,
                    remote_classification TEXT NOT NULL,
                    posted_at TEXT,
                    raw_description TEXT NOT NULL,
                    normalized_description TEXT NOT NULL,
                    raw_payload_json TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    last_scored_at TEXT,
                    last_surfaced_at TEXT,
                    latest_score INTEGER,
                    latest_verdict TEXT,
                    latest_score_json TEXT,
                    last_digest_run_id TEXT
                );
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    stats_json TEXT NOT NULL,
                    email_sent INTEGER NOT NULL,
                    email_subject TEXT NOT NULL
                );
                """
            )
            columns = {
                row["name"]
                for row in cursor.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "latest_score_json" not in columns:
                cursor.execute("ALTER TABLE jobs ADD COLUMN latest_score_json TEXT")
        self.connection.commit()

    def touch_job(self, job: JobRecord, now: datetime) -> None:
        row = self.get_job_state(job.identity)
        payload = (
            job.identity,
            job.source_name,
            job.source_job_id,
            job.canonical_url,
            job.apply_url,
            job.title,
            job.company,
            job.raw_location,
            job.normalized_location,
            job.remote_classification,
            job.posted_at,
            job.raw_description,
            job.normalized_description,
            json.dumps(job.raw_payload, sort_keys=True, default=str),
            now.isoformat(),
            now.isoformat(),
        )
        if row is None:
            self.connection.execute(
                """
                INSERT INTO jobs (
                    identity, source_name, source_job_id, canonical_url, apply_url, title, company,
                    raw_location, normalized_location, remote_classification, posted_at,
                    raw_description, normalized_description, raw_payload_json, first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )
        else:
            self.connection.execute(
                """
                UPDATE jobs
                SET source_name = ?, source_job_id = ?, canonical_url = ?, apply_url = ?, title = ?,
                    company = ?, raw_location = ?, normalized_location = ?, remote_classification = ?,
                    posted_at = ?, raw_description = ?, normalized_description = ?, raw_payload_json = ?,
                    last_seen_at = ?
                WHERE identity = ?
                """,
                (
                    job.source_name,
                    job.source_job_id,
                    job.canonical_url,
                    job.apply_url,
                    job.title,
                    job.company,
                    job.raw_location,
                    job.normalized_location,
                    job.remote_classification,
                    job.posted_at,
                    job.raw_description,
                    job.normalized_description,
                    json.dumps(job.raw_payload, sort_keys=True, default=str),
                    now.isoformat(),
                    job.identity,
                ),
            )
        self.connection.commit()

    def get_job_state(self, identity: str) -> JobState | None:
        row = self.connection.execute("SELECT * FROM jobs WHERE identity = ?", (identity,)).fetchone()
        if row is None:
            return None
        return JobState(
            identity=row["identity"],
            first_seen_at=_parse_datetime(row["first_seen_at"]),
            last_seen_at=_parse_datetime(row["last_seen_at"]),
            last_scored_at=_parse_datetime(row["last_scored_at"]),
            last_surfaced_at=_parse_datetime(row["last_surfaced_at"]),
            latest_score=row["latest_score"],
            latest_verdict=row["latest_verdict"],
            last_digest_run_id=row["last_digest_run_id"],
        )

    def eligible_for_resurface(self, identity: str, now: datetime, cooldown_days: int) -> bool:
        state = self.get_job_state(identity)
        if state is None or state.last_surfaced_at is None:
            return True
        return now - state.last_surfaced_at >= timedelta(days=cooldown_days)

    def record_score(self, identity: str, score: ScoreResult, now: datetime) -> None:
        self.connection.execute(
            """
            UPDATE jobs
            SET last_scored_at = ?, latest_score = ?, latest_verdict = ?, latest_score_json = ?
            WHERE identity = ?
            """,
            (
                now.isoformat(),
                score.fit_score,
                score.verdict,
                json.dumps(asdict(score), sort_keys=True),
                identity,
            ),
        )
        self.connection.commit()

    def record_surface(self, identity: str, run_id: str, now: datetime) -> None:
        self.connection.execute(
            """
            UPDATE jobs
            SET last_surfaced_at = ?, last_digest_run_id = ?
            WHERE identity = ?
            """,
            (now.isoformat(), run_id, identity),
        )
        self.connection.commit()

    def get_packet_jobs(self, *, since: datetime, digest_threshold: int) -> list[PacketJob]:
        rows = self.connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE last_scored_at IS NOT NULL
              AND last_scored_at >= ?
              AND latest_score >= ?
            """,
            (since.isoformat(), digest_threshold),
        ).fetchall()
        packet_jobs: list[PacketJob] = []
        for row in rows:
            score = _score_from_row(row)
            if score is None:
                continue
            packet_jobs.append(
                PacketJob(
                    job=JobRecord(
                        identity=row["identity"],
                        source_name=row["source_name"],
                        source_job_id=row["source_job_id"],
                        canonical_url=row["canonical_url"],
                        apply_url=row["apply_url"],
                        title=row["title"],
                        company=row["company"],
                        raw_location=row["raw_location"],
                        normalized_location=row["normalized_location"],
                        remote_classification=row["remote_classification"],
                        posted_at=row["posted_at"],
                        raw_description=row["raw_description"],
                        normalized_description=row["normalized_description"],
                        raw_payload=json.loads(row["raw_payload_json"]),
                        score=score,
                    ),
                    last_scored_at=_parse_datetime(row["last_scored_at"]) or since,
                )
            )
        return packet_jobs

    def record_run(
        self,
        run_id: str,
        started_at: datetime,
        completed_at: datetime,
        stats: RunStats,
        email_sent: bool,
        email_subject: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO runs (
                run_id, started_at, completed_at, stats_json, email_sent, email_subject
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                started_at.isoformat(),
                completed_at.isoformat(),
                json.dumps(asdict(stats), sort_keys=True),
                int(email_sent),
                email_subject,
            ),
        )
        self.connection.commit()


def utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _score_from_row(row: sqlite3.Row) -> ScoreResult | None:
    if row["latest_score_json"]:
        return ScoreResult(**json.loads(row["latest_score_json"]))
    if row["latest_score"] is None or row["latest_verdict"] is None:
        return None
    return ScoreResult(
        fit_score=row["latest_score"],
        verdict=row["latest_verdict"],
        matching_skills=[],
        gaps=[],
        seniority_alignment="",
        location_alignment="",
        reason_to_apply="",
        reason_to_skip="",
        short_digest_summary="",
    )
