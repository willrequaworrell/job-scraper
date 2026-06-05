from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from job_digest.config import Settings
from job_digest.models import JobRecord, ScoreResult


class ScorePayload(BaseModel):
    fit_score: int = Field(ge=0, le=100)
    verdict: str
    matching_skills: list[str]
    gaps: list[str]
    seniority_alignment: str
    location_alignment: str
    reason_to_apply: str
    reason_to_skip: str
    short_digest_summary: str


class OpenAIScorer:
    def __init__(self, api_key: str, model: str, profile_path: Path, policy_path: Path, system_prompt_path: Path) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai is required for scoring. Install project dependencies first.") from exc
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.profile_text = profile_path.read_text(encoding="utf-8")
        self.policy_text = policy_path.read_text(encoding="utf-8")
        self.system_prompt_text = system_prompt_path.read_text(encoding="utf-8")

    def score(self, job: JobRecord, settings: Settings) -> ScoreResult:
        completion = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self.system_prompt_text,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "candidate_profile": self.profile_text,
                            "scoring_policy": self.policy_text,
                            "digest_threshold": settings.scoring.digest_threshold,
                            "top_match_threshold": settings.scoring.top_match_threshold,
                            "job": {
                                "title": job.title,
                                "company": job.company,
                                "source_name": job.source_name,
                                "raw_location": job.raw_location,
                                "normalized_location": job.normalized_location,
                                "remote_classification": job.remote_classification,
                                "canonical_url": job.canonical_url,
                                "description": job.raw_description,
                            },
                            "expected_verdicts": settings.scoring.expected_verdicts,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            response_format=ScorePayload,
        )
        message = completion.choices[0].message
        if getattr(message, "refusal", None):
            raise RuntimeError(f"OpenAI refused to score job {job.identity}: {message.refusal}")
        parsed = message.parsed
        if parsed is None:
            raise RuntimeError(f"OpenAI returned no parsed payload for job {job.identity}")
        score = ScoreResult(**parsed.model_dump())
        usage = getattr(completion, "usage", None)
        if usage is not None:
            score.prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            score.completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
            score.total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
        return score
