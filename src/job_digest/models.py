from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ScoreResult:
    fit_score: int
    verdict: str
    matching_skills: list[str]
    gaps: list[str]
    seniority_alignment: str
    location_alignment: str
    reason_to_apply: str
    reason_to_skip: str
    short_digest_summary: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(slots=True)
class JobRecord:
    identity: str
    source_name: str
    source_job_id: str | None
    canonical_url: str
    apply_url: str
    title: str
    company: str
    raw_location: str
    normalized_location: str
    remote_classification: str
    posted_at: str | None
    raw_description: str
    normalized_description: str
    raw_payload: dict[str, Any]
    filter_reasons: list[str] = field(default_factory=list)
    score: ScoreResult | None = None

    def text_blob(self) -> str:
        return " ".join(
            part for part in [self.title, self.company, self.raw_location, self.normalized_description] if part
        ).lower()


@dataclass(slots=True)
class JobState:
    identity: str
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    last_scored_at: datetime | None
    last_surfaced_at: datetime | None
    latest_score: int | None
    latest_verdict: str | None
    last_digest_run_id: str | None


@dataclass(slots=True)
class PacketJob:
    job: JobRecord
    last_scored_at: datetime


@dataclass(slots=True)
class RunStats:
    fetched: int = 0
    normalized: int = 0
    suppressed: int = 0
    filtered: int = 0
    scored: int = 0
    passed: int = 0
    emailed: int = 0
    duplicate_records: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
