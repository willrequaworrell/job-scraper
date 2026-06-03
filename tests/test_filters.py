from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_digest.config import load_settings
from job_digest.filters import apply_rule_filters
from job_digest.models import JobRecord


def make_job(**overrides: object) -> JobRecord:
    payload = {
        "identity": "job-1",
        "source_name": "indeed",
        "source_job_id": "1",
        "canonical_url": "https://example.com/job-1",
        "apply_url": "https://example.com/job-1",
        "title": "Frontend Engineer",
        "company": "Example",
        "raw_location": "Boston, MA",
        "normalized_location": "boston, ma",
        "remote_classification": "onsite",
        "posted_at": None,
        "raw_description": "Build React and TypeScript applications.",
        "normalized_description": "build react and typescript applications.",
        "raw_payload": {},
    }
    payload.update(overrides)
    return JobRecord(**payload)


class FilterTests(TestCase):
    def setUp(self) -> None:
        self.settings = load_settings(Path(__file__).resolve().parents[1] / "config" / "settings.json")

    def test_rejects_too_senior_title(self) -> None:
        job = make_job(title="Principal Frontend Engineer")
        self.assertIn("excluded_title_seniority", apply_rule_filters(job, self.settings))

    def test_rejects_wrong_location(self) -> None:
        job = make_job(raw_location="Berlin, Germany", normalized_location="berlin, germany")
        self.assertIn("location_out_of_scope", apply_rule_filters(job, self.settings))

    def test_accepts_us_remote_role(self) -> None:
        job = make_job(
            raw_location="Remote - United States",
            normalized_location="remote",
            remote_classification="remote",
            raw_description="Remote US React role.",
            normalized_description="remote us react role.",
        )
        self.assertEqual(apply_rule_filters(job, self.settings), [])

    def test_rejects_required_experience_above_three_years(self) -> None:
        job = make_job(
            raw_description="Requires 4+ years of professional software engineering experience with React.",
            normalized_description="requires 4+ years of professional software engineering experience with react.",
        )
        self.assertIn("required_experience_too_high", apply_rule_filters(job, self.settings))

    def test_does_not_reject_low_or_preferred_years_of_experience(self) -> None:
        job = make_job(
            raw_description="0-3 years of experience accepted. 5+ years preferred. React role.",
            normalized_description="0-3 years of experience accepted. 5+ years preferred. react role.",
        )
        self.assertNotIn("required_experience_too_high", apply_rule_filters(job, self.settings))
