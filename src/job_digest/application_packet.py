from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

from job_digest.config import Settings
from job_digest.models import PacketJob


def default_packet_path(now: datetime) -> Path:
    return Path("artifacts") / "application_packets" / f"{now.date().isoformat()}.md"


def build_packet_subject(packet_jobs: list[PacketJob]) -> str:
    if not packet_jobs:
        return "Weekly job application packet: no passing jobs"
    noun = "job" if len(packet_jobs) == 1 else "jobs"
    return f"Weekly job application packet: {len(packet_jobs)} passing {noun}"


def sort_packet_jobs(packet_jobs: list[PacketJob], settings: Settings) -> list[PacketJob]:
    return sorted(
        packet_jobs,
        key=lambda packet_job: (
            packet_job.job.score is not None
            and packet_job.job.score.fit_score >= settings.scoring.top_match_threshold,
            packet_job.job.score.fit_score if packet_job.job.score else 0,
            packet_job.last_scored_at,
        ),
        reverse=True,
    )


def render_application_packet_markdown(
    packet_jobs: list[PacketJob],
    *,
    settings: Settings,
    application_profile: str,
    generated_at: datetime,
    window_days: int,
) -> str:
    top_matches = [
        packet_job
        for packet_job in packet_jobs
        if packet_job.job.score and packet_job.job.score.fit_score >= settings.scoring.top_match_threshold
    ]
    lines = [
        "# Weekly Job Application Packet",
        "",
        f"Generated: {generated_at.isoformat()}",
        f"Window: last {window_days} days",
        f"Passing threshold: {settings.scoring.digest_threshold}",
        f"Top-match threshold: {settings.scoring.top_match_threshold}",
        f"Passing jobs: {len(packet_jobs)}",
        f"Top matches: {len(top_matches)}",
        "",
        "## Comet Instructions",
        "",
        "- Use only the application profile and job-specific notes in this packet.",
        "- Do not invent missing facts, dates, credentials, compensation history, or personal details.",
        "- If a required field is missing or ambiguous, stop and ask Will.",
        "- You may fill forms and draft answers, but do not submit any application without Will's review.",
        "- Do not autofill SSN, date of birth, document IDs, passwords, payment details, or tax details.",
        "",
        "## Application Profile",
        "",
        application_profile.strip(),
        "",
        "## Jobs",
        "",
    ]
    if not packet_jobs:
        lines.extend(["No jobs met the configured threshold during this packet window.", ""])
        return "\n".join(lines)

    for index, packet_job in enumerate(sort_packet_jobs(packet_jobs, settings), start=1):
        job = packet_job.job
        score = job.score
        score_value = score.fit_score if score else 0
        label = "TOP MATCH" if score_value >= settings.scoring.top_match_threshold else "PASSING MATCH"
        lines.extend(
            [
                f"### {index}. {job.title} at {job.company}",
                "",
                f"- Label: {label}",
                f"- Fit score: {score_value}/100",
                f"- Verdict: {score.verdict if score else ''}",
                f"- Source: {job.source_name}",
                f"- Location: {job.raw_location or job.normalized_location}",
                f"- Remote classification: {job.remote_classification}",
                f"- Posted at: {job.posted_at or 'unknown'}",
                f"- Last scored at: {packet_job.last_scored_at.isoformat()}",
                f"- Apply URL: {job.apply_url or job.canonical_url}",
                "",
                f"Summary: {score.short_digest_summary if score else ''}",
                "",
                "Application emphasis:",
                f"- Reason to apply: {score.reason_to_apply if score else ''}",
                f"- Reason to skip/watch: {score.reason_to_skip if score else ''}",
                f"- Seniority alignment: {score.seniority_alignment if score else ''}",
                f"- Location alignment: {score.location_alignment if score else ''}",
                "",
                "Matching skills:",
                *_bullet_lines(score.matching_skills if score else []),
                "",
                "Gaps to avoid overstating:",
                *_bullet_lines(score.gaps if score else []),
                "",
            ]
        )
    return "\n".join(lines)


def render_application_packet_html(markdown: str) -> str:
    parts = ["<html><body>"]
    in_list = False
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line:
            if in_list:
                parts.append("</ul>")
                in_list = False
            continue
        if line.startswith("- "):
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{_linkify(escape(line[2:]))}</li>")
            continue
        if in_list:
            parts.append("</ul>")
            in_list = False
        if line.startswith("# "):
            parts.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("## "):
            parts.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("### "):
            parts.append(f"<h3>{escape(line[4:])}</h3>")
        else:
            parts.append(f"<p>{_linkify(escape(line))}</p>")
    if in_list:
        parts.append("</ul>")
    parts.append("</body></html>")
    return "".join(parts)


def _bullet_lines(items: list[str]) -> list[str]:
    if not items:
        return ["- None listed."]
    return [f"- {item}" for item in items]


def _linkify(text: str) -> str:
    words = []
    for word in text.split(" "):
        if word.startswith("http://") or word.startswith("https://"):
            words.append(f"<a href='{word}'>{word}</a>")
        else:
            words.append(word)
    return " ".join(words)
