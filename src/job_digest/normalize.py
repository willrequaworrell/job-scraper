from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from job_digest.models import JobRecord


def normalize_job(raw: dict) -> JobRecord:
    source_name = str(raw.get("site") or raw.get("site_name") or raw.get("source") or "unknown").strip().lower()
    source_job_id = _clean_nullable(raw.get("id") or raw.get("job_id"))
    canonical_url = _canonicalize_url(raw.get("job_url") or raw.get("url") or raw.get("job_url_direct"))
    apply_url = _canonicalize_url(raw.get("job_url_direct") or raw.get("job_url") or raw.get("url"))
    title = _clean_text(raw.get("title"))
    company = _clean_text(raw.get("company"))
    raw_location = _clean_text(raw.get("location"))
    raw_description = _clean_text(raw.get("description") or raw.get("job_description"))
    normalized_description = _normalize_text(raw_description)
    remote_classification = _classify_remote(raw_location, raw_description)
    normalized_location = _normalize_location(raw_location, remote_classification)
    posted_at = _clean_nullable(raw.get("date_posted") or raw.get("posted_at"))
    identity = build_identity(source_name, source_job_id, canonical_url, title, company)

    return JobRecord(
        identity=identity,
        source_name=source_name,
        source_job_id=source_job_id,
        canonical_url=canonical_url or "",
        apply_url=apply_url or canonical_url or "",
        title=title,
        company=company,
        raw_location=raw_location,
        normalized_location=normalized_location,
        remote_classification=remote_classification,
        posted_at=posted_at,
        raw_description=raw_description,
        normalized_description=normalized_description,
        raw_payload={str(key): value for key, value in raw.items()},
    )


def build_identity(
    source_name: str, source_job_id: str | None, canonical_url: str, title: str, company: str
) -> str:
    if source_job_id:
        return f"{source_name}:{source_job_id}"
    if canonical_url:
        return f"{source_name}:{canonical_url}"
    fallback = "|".join([source_name, title.lower(), company.lower()])
    return f"{source_name}:hash:{hashlib.sha256(fallback.encode('utf-8')).hexdigest()[:16]}"


def _canonicalize_url(value: object) -> str:
    if not value:
        return ""
    raw_url = str(value).strip()
    if not raw_url:
        return ""
    parsed = urlparse(raw_url)
    query = _canonical_query(parsed)
    cleaned = parsed._replace(query=query, fragment="")
    path = re.sub(r"/+$", "", cleaned.path or "")
    cleaned = cleaned._replace(path=path)
    return urlunparse(cleaned)


def _canonical_query(parsed) -> str:
    host = parsed.netloc.lower()
    path = parsed.path or ""
    if "indeed.com" in host and path.rstrip("/") == "/viewjob":
        kept = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=False) if key in {"jk", "vjk"}]
        return urlencode(kept)
    return ""


def _clean_nullable(value: object) -> str | None:
    text = _clean_text(value)
    return text or None


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _classify_remote(location: str, description: str) -> str:
    blob = f"{location} {description}".lower()
    if "hybrid" in blob:
        return "hybrid"
    if "remote" in blob or "work from home" in blob:
        return "remote"
    return "onsite"


def _normalize_location(location: str, remote_classification: str) -> str:
    if remote_classification == "remote":
        return "remote"
    cleaned = location.lower()
    cleaned = cleaned.replace("massachusetts", "ma")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned
