from __future__ import annotations

import re

from job_digest.config import Settings
from job_digest.models import JobRecord


def apply_rule_filters(job: JobRecord, settings: Settings) -> list[str]:
    reasons: list[str] = []
    title_blob = job.title.lower()
    if any(term in title_blob for term in settings.title_exclusion_terms):
        reasons.append("excluded_title_seniority")

    if _has_required_experience_above_limit(job.normalized_description, max_years=3):
        reasons.append("required_experience_too_high")

    text_blob = job.text_blob()
    if not any(keyword in text_blob for keyword in settings.keyword_include_any):
        reasons.append("missing_target_keywords")

    if not _is_location_allowed(job, settings):
        reasons.append("location_out_of_scope")

    return reasons


def _is_location_allowed(job: JobRecord, settings: Settings) -> bool:
    location_blob = f"{job.raw_location} {job.normalized_description}".lower()

    if job.remote_classification == "remote":
        if not settings.location.allow_remote:
            return False
        if any(term in location_blob for term in settings.location.rejected_remote_terms):
            return False
        if any(term in location_blob for term in settings.location.accepted_us_terms):
            return True
        return "remote" in location_blob or "work from home" in location_blob

    return any(_contains_term(location_blob, term) for term in settings.location.accepted_local_terms)


def _contains_term(blob: str, term: str) -> bool:
    escaped = re.escape(term.lower())
    return re.search(rf"(?<!\w){escaped}(?!\w)", blob) is not None


def _has_required_experience_above_limit(description: str, *, max_years: int) -> bool:
    # Treat explicit minimum requirements above the target band as a cheap hard gate.
    patterns = [
        r"(\d+)\s*\+\s*years? of [^.]{0,80}?experience",
        r"minimum of (\d+)\s+years? of [^.]{0,80}?experience",
        r"at least (\d+)\s+years? of [^.]{0,80}?experience",
        r"(\d+)\s*-\s*\d+\s+years? of [^.]{0,80}?experience",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, description):
            years = int(match.group(1))
            window_start = max(0, match.start() - 60)
            context = description[window_start : match.end() + 60]
            if "preferred" in context or "ideally" in context or "nice to have" in context:
                continue
            if years > max_years:
                return True
    return False
