from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_digest.normalize import build_identity, normalize_job


class NormalizeTests(TestCase):
    def test_prefers_source_job_id_for_identity(self) -> None:
        identity = build_identity("indeed", "abc123", "https://example.com/job", "Frontend Engineer", "Example")
        self.assertEqual(identity, "indeed:abc123")

    def test_falls_back_to_canonical_url(self) -> None:
        identity = build_identity("google", None, "https://example.com/job", "Frontend Engineer", "Example")
        self.assertEqual(identity, "google:https://example.com/job")

    def test_normalizes_urls_and_remote_classification(self) -> None:
        job = normalize_job(
            {
                "site": "Indeed",
                "job_url": "https://example.com/job?utm_source=test",
                "job_url_direct": "https://example.com/job/apply?src=test",
                "title": "Frontend Engineer",
                "company": "Example",
                "location": "Remote - United States",
                "description": "Remote React role",
            }
        )
        self.assertEqual(job.canonical_url, "https://example.com/job")
        self.assertEqual(job.remote_classification, "remote")

    def test_preserves_indeed_job_key_in_viewjob_url(self) -> None:
        job = normalize_job(
            {
                "site": "Indeed",
                "job_url": "https://www.indeed.com/viewjob?jk=abc123&utm_source=test",
                "title": "Frontend Engineer",
                "company": "Example",
                "location": "Boston, MA",
                "description": "React role",
            }
        )
        self.assertEqual(job.canonical_url, "https://www.indeed.com/viewjob?jk=abc123")
