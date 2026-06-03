from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from job_digest.application_packet import (
    build_packet_subject,
    default_packet_path,
    render_application_packet_html,
    render_application_packet_markdown,
)
from job_digest.config import Settings, load_runtime_env, load_settings
from job_digest.digest import build_subject, render_digest_html
from job_digest.emailer import ResendEmailer
from job_digest.fetcher import fetch_jobs
from job_digest.filters import apply_rule_filters
from job_digest.models import JobRecord, RunStats
from job_digest.normalize import normalize_job
from job_digest.persistence import StateStore, utc_now
from job_digest.scoring import OpenAIScorer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the job digest batch workflow.")
    parser.add_argument("--config", default="config/settings.json", help="Path to committed settings JSON.")
    parser.add_argument("--profile", default="resume.md", help="Path to the curated candidate profile file.")
    parser.add_argument("--policy", default="scoring_policy.md", help="Path to the generic scoring policy file.")
    parser.add_argument("--db-path", default="data/job_digest.sqlite", help="Path to the tracked SQLite state file.")
    parser.add_argument("--dry-run", action="store_true", help="Skip email delivery and state mutation after scoring.")
    parser.add_argument("--delivery", choices=["email", "none"], default="email", help="Delivery mode for durable runs.")
    parser.add_argument(
        "--application-profile",
        default="application_profile.md",
        help="Path to the editable application profile used in weekly packets.",
    )
    parser.add_argument(
        "--write-application-packet",
        action="store_true",
        help="Write and optionally email a weekly application packet from recent scored jobs.",
    )
    parser.add_argument("--packet-output", default=None, help="Path for the generated application packet Markdown.")
    parser.add_argument("--packet-window-days", type=int, default=7, help="Recent scored-job window for packets.")
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args()
    settings = load_settings(Path(args.config))
    runtime = load_runtime_env()
    started_at = utc_now()
    run_id = started_at.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    stats = RunStats()

    scorer = OpenAIScorer(
        runtime.openai_api_key,
        settings.scoring.openai_model,
        Path(args.profile),
        Path(args.policy),
        Path(settings.scoring.system_prompt_path),
    )
    emailer = ResendEmailer(runtime.resend_api_key) if args.delivery == "email" else None
    store = StateStore(Path(args.db_path))

    try:
        raw_jobs = fetch_jobs(settings)
        stats.fetched = len(raw_jobs)
        jobs = _normalize_unique_jobs(raw_jobs, stats)
        stats.normalized = len(jobs)
        selected_jobs: list[JobRecord] = []
        job_results: list[dict[str, object]] = []

        for job in jobs:
            now = utc_now()
            if not args.dry_run:
                store.touch_job(job, now)
                if (
                    not runtime.disable_resurface_suppression
                    and not store.eligible_for_resurface(job.identity, now, settings.resurface_after_days)
                ):
                    stats.suppressed += 1
                    job_results.append(_build_job_result(job, outcome="suppressed"))
                    continue

            reasons = apply_rule_filters(job, settings)
            job.filter_reasons = reasons
            if reasons:
                stats.filtered += 1
                logging.info("Filtered %s for reasons: %s", job.identity, ",".join(reasons))
                job_results.append(_build_job_result(job, outcome="filtered"))
                continue

            job.score = scorer.score(job, settings)
            stats.scored += 1
            if not args.dry_run:
                store.record_score(job.identity, job.score, now)

            outcome = "passed" if job.score.fit_score >= settings.scoring.digest_threshold else "scored_below_threshold"
            job_results.append(_build_job_result(job, outcome=outcome))
            if job.score.fit_score >= settings.scoring.digest_threshold:
                selected_jobs.append(job)

        stats.passed = len(selected_jobs)
        subject = build_subject(len(selected_jobs))
        html = render_digest_html(selected_jobs, settings)

        if args.dry_run:
            _write_debug_output(
                runtime.debug_output_path,
                run_id=run_id,
                started_at=started_at,
                completed_at=utc_now(),
                stats=stats,
                settings_digest_threshold=settings.scoring.digest_threshold,
                email_sent=False,
                email_subject=subject,
                jobs=job_results,
            )
            logging.info("Dry run complete. %s jobs passed threshold.", len(selected_jobs))
            return 0

        email_sent = False
        if args.write_application_packet:
            packet_generated_at = utc_now()
            packet_subject, packet_html, packet_job_count = _write_application_packet(
                store=store,
                settings=settings,
                application_profile_path=Path(args.application_profile),
                output_path=Path(args.packet_output) if args.packet_output else default_packet_path(packet_generated_at),
                generated_at=packet_generated_at,
                window_days=args.packet_window_days,
            )
            subject = packet_subject
            if args.delivery == "email" and emailer is not None:
                emailer.send(sender=settings.email_from, recipient=runtime.email_to, subject=packet_subject, html=packet_html)
                email_sent = True
                stats.emailed = packet_job_count
        elif args.delivery == "email" and (selected_jobs or settings.send_empty_digest) and emailer is not None:
            emailer.send(sender=settings.email_from, recipient=runtime.email_to, subject=subject, html=html)
            email_sent = True
            stats.emailed = len(selected_jobs)
            surfaced_at = utc_now()
            for job in selected_jobs:
                store.record_surface(job.identity, run_id, surfaced_at)

        completed_at = utc_now()
        store.record_run(run_id, started_at, completed_at, stats, email_sent, subject)
        _write_debug_output(
            runtime.debug_output_path,
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            stats=stats,
            settings_digest_threshold=settings.scoring.digest_threshold,
            email_sent=email_sent,
            email_subject=subject,
            jobs=job_results,
        )
        logging.info("Run complete. Stats=%s", asdict(stats))
        return 0
    finally:
        store.close()


def _normalize_unique_jobs(raw_jobs: list[dict], stats: RunStats) -> list[JobRecord]:
    deduped: dict[str, JobRecord] = {}
    for raw in raw_jobs:
        job = normalize_job(raw)
        if job.identity in deduped:
            stats.duplicate_records += 1
            continue
        deduped[job.identity] = job
    return list(deduped.values())


def _build_job_result(job: JobRecord, *, outcome: str) -> dict[str, object]:
    return {
        "identity": job.identity,
        "outcome": outcome,
        "source_name": job.source_name,
        "source_job_id": job.source_job_id,
        "canonical_url": job.canonical_url,
        "apply_url": job.apply_url,
        "title": job.title,
        "company": job.company,
        "raw_location": job.raw_location,
        "normalized_location": job.normalized_location,
        "remote_classification": job.remote_classification,
        "posted_at": job.posted_at,
        "filter_reasons": job.filter_reasons,
        "score": asdict(job.score) if job.score else None,
        "raw_description": job.raw_description,
    }


def _write_application_packet(
    *,
    store: StateStore,
    settings: Settings,
    application_profile_path: Path,
    output_path: Path,
    generated_at: datetime,
    window_days: int,
) -> tuple[str, str, int]:
    since = generated_at - timedelta(days=window_days)
    packet_jobs = store.get_packet_jobs(since=since, digest_threshold=settings.scoring.digest_threshold)
    application_profile = application_profile_path.read_text(encoding="utf-8")
    markdown = render_application_packet_markdown(
        packet_jobs,
        settings=settings,
        application_profile=application_profile,
        generated_at=generated_at,
        window_days=window_days,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    surfaced_at = utc_now()
    run_id = generated_at.strftime("%Y%m%dT%H%M%SZ") + "-packet"
    for packet_job in packet_jobs:
        store.record_surface(packet_job.job.identity, run_id, surfaced_at)
    return build_packet_subject(packet_jobs), render_application_packet_html(markdown), len(packet_jobs)


def _write_debug_output(
    output_path: str | None,
    *,
    run_id: str,
    started_at,
    completed_at,
    stats: RunStats,
    settings_digest_threshold: int,
    email_sent: bool,
    email_subject: str,
    jobs: list[dict[str, object]],
) -> None:
    if not output_path:
        return
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "digest_threshold": settings_digest_threshold,
        "email_sent": email_sent,
        "email_subject": email_subject,
        "stats": asdict(stats),
        "jobs": jobs,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
