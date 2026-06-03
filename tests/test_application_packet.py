from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_digest.application_packet import (
    build_packet_subject,
    render_application_packet_html,
    render_application_packet_markdown,
)
from job_digest.config import load_settings
from job_digest.models import JobRecord, PacketJob, ScoreResult


def make_packet_job(score: int) -> PacketJob:
    return PacketJob(
        job=JobRecord(
            identity="indeed:123",
            source_name="indeed",
            source_job_id="123",
            canonical_url="https://example.com/job",
            apply_url="https://example.com/apply",
            title="Frontend Engineer",
            company="Example Co",
            raw_location="Boston, MA",
            normalized_location="boston, ma",
            remote_classification="hybrid",
            posted_at="2026-06-01",
            raw_description="React and TypeScript role",
            normalized_description="react and typescript role",
            raw_payload={},
            score=ScoreResult(
                fit_score=score,
                verdict="strong_match",
                matching_skills=["React", "TypeScript"],
                gaps=["No major gaps"],
                seniority_alignment="aligned",
                location_alignment="aligned",
                reason_to_apply="Strong frontend overlap.",
                reason_to_skip="None.",
                short_digest_summary="Strong product-facing frontend fit.",
            ),
        ),
        last_scored_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )


class ApplicationPacketTests(TestCase):
    def setUp(self) -> None:
        self.settings = load_settings(Path(__file__).resolve().parents[1] / "config" / "settings.json")

    def test_packet_renders_profile_instructions_and_top_match(self) -> None:
        markdown = render_application_packet_markdown(
            [make_packet_job(88)],
            settings=self.settings,
            application_profile="Profile facts",
            generated_at=datetime(2026, 6, 2, 12, 0, tzinfo=UTC),
            window_days=7,
        )

        self.assertIn("Do not invent missing facts", markdown)
        self.assertIn("do not submit any application without Will's review", markdown)
        self.assertIn("Profile facts", markdown)
        self.assertIn("Label: TOP MATCH", markdown)
        self.assertIn("Apply URL: https://example.com/apply", markdown)
        self.assertEqual(build_packet_subject([make_packet_job(88)]), "Weekly job application packet: 1 passing job")

        html = render_application_packet_html(markdown)
        self.assertIn("<h1>Weekly Job Application Packet</h1>", html)
        self.assertIn("<a href='https://example.com/apply'>https://example.com/apply</a>", html)
