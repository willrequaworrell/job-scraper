from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_digest.config import load_settings
from job_digest.digest import build_subject, render_digest_html
from job_digest.models import JobRecord, ScoreResult


class DigestTests(TestCase):
    def setUp(self) -> None:
        self.settings = load_settings(Path(__file__).resolve().parents[1] / "config" / "settings.json")

    def test_empty_digest_uses_no_match_copy(self) -> None:
        html = render_digest_html([], self.settings)
        self.assertIn("No jobs met the configured threshold", html)
        self.assertEqual(build_subject(0), "Job digest: no strong matches this run")

    def test_digest_renders_selected_job(self) -> None:
        job = JobRecord(
            identity="indeed:123",
            source_name="indeed",
            source_job_id="123",
            canonical_url="https://example.com/job",
            apply_url="https://example.com/job",
            title="Frontend Engineer",
            company="Example Co",
            raw_location="Boston, MA",
            normalized_location="boston, ma",
            remote_classification="hybrid",
            posted_at=None,
            raw_description="React and TypeScript role",
            normalized_description="react and typescript role",
            raw_payload={},
            score=ScoreResult(
                fit_score=88,
                verdict="strong_match",
                matching_skills=["React", "TypeScript"],
                gaps=["None"],
                seniority_alignment="aligned",
                location_alignment="aligned",
                reason_to_apply="Strong frontend overlap.",
                reason_to_skip="None.",
                short_digest_summary="Strong product-facing frontend fit.",
            ),
        )
        html = render_digest_html([job], self.settings)
        self.assertIn("Frontend Engineer at Example Co", html)
        self.assertIn("88/100", html)
