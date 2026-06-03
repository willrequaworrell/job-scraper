from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class LocationConfig:
    allow_remote: bool
    accepted_local_terms: list[str]
    accepted_remote_terms: list[str]
    accepted_us_terms: list[str]
    rejected_remote_terms: list[str]


@dataclass(slots=True)
class ScoringConfig:
    digest_threshold: int
    top_match_threshold: int
    openai_model: str
    system_prompt_path: str
    expected_verdicts: list[str]


@dataclass(slots=True)
class Settings:
    search_terms: list[str]
    sites: list[str]
    hours_old: int
    results_per_search: int
    country_indeed: str
    google_search_location: str
    title_exclusion_terms: list[str]
    keyword_include_any: list[str]
    resurface_after_days: int
    send_empty_digest: bool
    email_from: str
    scoring: ScoringConfig
    location: LocationConfig


@dataclass(slots=True)
class RuntimeEnv:
    openai_api_key: str
    resend_api_key: str
    email_to: str
    disable_resurface_suppression: bool
    debug_output_path: str | None


def load_settings(path: Path) -> Settings:
    payload = json.loads(path.read_text(encoding="utf-8"))
    location = LocationConfig(**payload["location"])
    scoring = ScoringConfig(**payload["scoring"])
    return Settings(
        search_terms=payload["search_terms"],
        sites=payload["sites"],
        hours_old=payload["hours_old"],
        results_per_search=payload["results_per_search"],
        country_indeed=payload["country_indeed"],
        google_search_location=payload["google_search_location"],
        title_exclusion_terms=[term.lower() for term in payload["title_exclusion_terms"]],
        keyword_include_any=[term.lower() for term in payload["keyword_include_any"]],
        resurface_after_days=payload["resurface_after_days"],
        send_empty_digest=payload["send_empty_digest"],
        email_from=payload["email_from"],
        scoring=scoring,
        location=location,
    )


def load_runtime_env() -> RuntimeEnv:
    missing = [key for key in ("OPENAI_API_KEY", "RESEND_API_KEY", "EMAIL_TO") if not os.getenv(key)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
    return RuntimeEnv(
        openai_api_key=os.environ["OPENAI_API_KEY"],
        resend_api_key=os.environ["RESEND_API_KEY"],
        email_to=os.environ["EMAIL_TO"],
        disable_resurface_suppression=_env_flag("JOB_DIGEST_DISABLE_RESURFACE_SUPPRESSION"),
        debug_output_path=_optional_env("JOB_DIGEST_DEBUG_OUTPUT_PATH"),
    )


def _env_flag(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _optional_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None
