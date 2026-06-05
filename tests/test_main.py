from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_digest.config import load_settings
from job_digest.main import _normalize_unique_jobs, _write_daily_summary, _write_debug_output, build_parser
from job_digest.models import RunStats, ScoreResult


class MainTests(TestCase):
    def test_parser_accepts_delivery_and_packet_flags(self) -> None:
        args = build_parser().parse_args(
            [
                "--delivery",
                "none",
                "--write-application-packet",
                "--packet-output",
                "artifacts/application_packets/test.md",
                "--packet-window-days",
                "7",
            ]
        )

        self.assertEqual(args.delivery, "none")
        self.assertTrue(args.write_application_packet)
        self.assertEqual(args.packet_output, "artifacts/application_packets/test.md")
        self.assertEqual(args.packet_window_days, 7)

    def test_normalize_unique_jobs_dedupes_by_identity(self) -> None:
        raw_jobs = [
            {
                "site": "Indeed",
                "id": "123",
                "job_url": "https://example.com/job?utm=one",
                "title": "Frontend Engineer",
                "company": "Example",
                "location": "Boston, MA",
                "description": "React role",
            },
            {
                "site": "Indeed",
                "id": "123",
                "job_url": "https://example.com/job?utm=two",
                "title": "Frontend Engineer",
                "company": "Example",
                "location": "Boston, MA",
                "description": "React role",
            },
        ]
        stats = RunStats()

        jobs = _normalize_unique_jobs(raw_jobs, stats)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(stats.duplicate_records, 1)

    def test_write_debug_output_persists_run_artifact(self) -> None:
        stats = RunStats(fetched=10, normalized=8, filtered=3, scored=5, passed=2)
        started_at = datetime(2026, 5, 10, 15, 0, 0, tzinfo=UTC)
        completed_at = datetime(2026, 5, 10, 15, 5, 0, tzinfo=UTC)
        jobs = [{"identity": "indeed:1", "outcome": "filtered", "filter_reasons": ["missing_target_keywords"]}]

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "artifacts" / "last_run.json"
            _write_debug_output(
                str(output_path),
                run_id="run-1",
                started_at=started_at,
                completed_at=completed_at,
                stats=stats,
                settings_digest_threshold=70,
                email_sent=False,
                email_subject="Job digest: no strong matches this run",
                jobs=jobs,
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["run_id"], "run-1")
        self.assertEqual(payload["digest_threshold"], 70)
        self.assertFalse(payload["email_sent"])
        self.assertEqual(payload["stats"], asdict(stats))
        self.assertEqual(payload["jobs"], jobs)

    def test_write_daily_summary_lists_passing_jobs_compactly(self) -> None:
        settings = load_settings(Path(__file__).resolve().parents[1] / "config" / "settings.json")
        stats = RunStats(fetched=10, normalized=8, filtered=3, scored=5, passed=1, duplicate_records=2, total_tokens=1234)
        started_at = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)
        completed_at = datetime(2026, 6, 5, 12, 5, 0, tzinfo=UTC)
        score = ScoreResult(
            fit_score=88,
            verdict="strong_match",
            matching_skills=["React"],
            gaps=[],
            seniority_alignment="aligned",
            location_alignment="aligned",
            reason_to_apply="Strong fit",
            reason_to_skip="None",
            short_digest_summary="Strong frontend fit.",
        )
        jobs = [
            {
                "identity": "indeed:1",
                "outcome": "passed",
                "title": "Frontend Engineer",
                "company": "Example",
                "raw_location": "Boston, MA",
                "normalized_location": "boston, ma",
                "apply_url": "https://example.com/apply",
                "canonical_url": "https://example.com/job",
                "score": asdict(score),
            }
        ]

        with TemporaryDirectory() as temp_dir:
            cwd = Path.cwd()
            try:
                import os

                os.chdir(temp_dir)
                path = _write_daily_summary(
                    run_id="run-1",
                    started_at=started_at,
                    completed_at=completed_at,
                    stats=stats,
                    settings=settings,
                    jobs=jobs,
                )
                content = path.read_text(encoding="utf-8")
            finally:
                os.chdir(cwd)

        self.assertIn("Scored jobs: 5", content)
        self.assertIn("Total LLM tokens: 1,234", content)
        self.assertIn("[TOP] 88/100 - Frontend Engineer at Example - Boston, MA - [link](https://example.com/apply)", content)
        self.assertNotIn("Fetched:", content)
        self.assertNotIn("Strong frontend fit.", content)
