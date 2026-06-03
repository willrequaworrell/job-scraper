from __future__ import annotations

import sys
import tempfile
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_digest.models import JobRecord, ScoreResult
from job_digest.persistence import StateStore


def make_job() -> JobRecord:
    return JobRecord(
        identity="indeed:1",
        source_name="indeed",
        source_job_id="1",
        canonical_url="https://example.com/job",
        apply_url="https://example.com/job",
        title="Frontend Engineer",
        company="Example",
        raw_location="Boston, MA",
        normalized_location="boston, ma",
        remote_classification="onsite",
        posted_at=None,
        raw_description="React role",
        normalized_description="react role",
        raw_payload={},
    )


class PersistenceTests(TestCase):
    def test_resurface_requires_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = StateStore(Path(temp_dir) / "state.sqlite")
            try:
                now = __import__("datetime").datetime.now(__import__("datetime").UTC)
                job = make_job()
                store.touch_job(job, now)
                self.assertTrue(store.eligible_for_resurface(job.identity, now, 7))
                score = ScoreResult(
                    fit_score=90,
                    verdict="strong_match",
                    matching_skills=[],
                    gaps=[],
                    seniority_alignment="aligned",
                    location_alignment="aligned",
                    reason_to_apply="Good fit",
                    reason_to_skip="None",
                    short_digest_summary="Good fit",
                )
                store.record_score(job.identity, score, now)
                store.record_surface(job.identity, "run-1", now)
                self.assertFalse(store.eligible_for_resurface(job.identity, now, 7))
                later = now + __import__("datetime").timedelta(days=8)
                self.assertTrue(store.eligible_for_resurface(job.identity, later, 7))
            finally:
                store.close()

    def test_get_packet_jobs_returns_recent_passing_scored_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = StateStore(Path(temp_dir) / "state.sqlite")
            try:
                now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
                passing = make_job()
                store.touch_job(passing, now)
                store.record_score(
                    passing.identity,
                    ScoreResult(
                        fit_score=88,
                        verdict="strong_match",
                        matching_skills=["React"],
                        gaps=["None"],
                        seniority_alignment="aligned",
                        location_alignment="aligned",
                        reason_to_apply="Strong fit",
                        reason_to_skip="No major gaps",
                        short_digest_summary="Strong frontend fit.",
                    ),
                    now,
                )
                stale = replace(passing, identity="indeed:stale", source_job_id="stale")
                store.touch_job(stale, now - timedelta(days=10))
                store.record_score(
                    stale.identity,
                    ScoreResult(
                        fit_score=95,
                        verdict="strong_match",
                        matching_skills=[],
                        gaps=[],
                        seniority_alignment="aligned",
                        location_alignment="aligned",
                        reason_to_apply="Strong fit",
                        reason_to_skip="No major gaps",
                        short_digest_summary="Stale fit.",
                    ),
                    now - timedelta(days=10),
                )

                packet_jobs = store.get_packet_jobs(since=now - timedelta(days=7), digest_threshold=70)

                self.assertEqual(len(packet_jobs), 1)
                self.assertEqual(packet_jobs[0].job.identity, passing.identity)
                self.assertEqual(packet_jobs[0].job.score.fit_score, 88)
                self.assertEqual(packet_jobs[0].job.score.matching_skills, ["React"])
            finally:
                store.close()
