from __future__ import annotations

from html import escape

from job_digest.config import Settings
from job_digest.models import JobRecord


def build_subject(job_count: int) -> str:
    if job_count == 0:
        return "Job digest: no strong matches this run"
    noun = "match" if job_count == 1 else "matches"
    return f"Job digest: {job_count} strong {noun}"


def render_digest_html(jobs: list[JobRecord], settings: Settings) -> str:
    if not jobs:
        return (
            "<html><body>"
            "<p>No jobs met the configured threshold on this run.</p>"
            "<p>The pipeline completed successfully and will check again on the next schedule.</p>"
            "</body></html>"
        )

    parts = [
        "<html><body>",
        f"<p>{len(jobs)} job(s) passed the digest threshold of {settings.scoring.digest_threshold}.</p>",
    ]
    for job in jobs:
        score = job.score
        score_badge = f"{score.fit_score}/100" if score else "unscored"
        summary = escape(score.short_digest_summary if score else "")
        apply_url = escape(job.apply_url or job.canonical_url)
        parts.append(
            "<section style='border:1px solid #ddd;border-radius:8px;padding:16px;margin:0 0 16px 0;'>"
            f"<h2 style='margin:0 0 8px 0;'>{escape(job.title)} at {escape(job.company)}</h2>"
            f"<p style='margin:0 0 8px 0;'><strong>Source:</strong> {escape(job.source_name.title())}<br>"
            f"<strong>Location:</strong> {escape(job.raw_location or job.normalized_location)}<br>"
            f"<strong>Remote:</strong> {escape(job.remote_classification)}<br>"
            f"<strong>Fit score:</strong> {escape(score_badge)}</p>"
            f"<p style='margin:0 0 8px 0;'>{summary}</p>"
            f"<ul style='margin:0 0 8px 20px;'>"
            f"<li>{escape(score.reason_to_apply if score else '')}</li>"
            f"<li>{escape(score.reason_to_skip if score else '')}</li>"
            "</ul>"
            f"<p style='margin:0;'><a href='{apply_url}'>Open application</a></p>"
            "</section>"
        )
    parts.append("</body></html>")
    return "".join(parts)
