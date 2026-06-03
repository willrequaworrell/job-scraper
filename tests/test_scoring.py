from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_digest.config import load_settings
from job_digest.main import build_parser
from job_digest.models import JobRecord
from job_digest.scoring import OpenAIScorer


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


class FakeOpenAI:
    next_message = None
    last_api_key = None
    last_parse_kwargs = None

    def __init__(self, api_key: str) -> None:
        type(self).last_api_key = api_key
        type(self).last_parse_kwargs = None
        self.beta = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    parse=self._parse,
                )
            )
        )

    def _parse(self, **kwargs: object) -> object:
        type(self).last_parse_kwargs = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=type(self).next_message)])


def install_fake_openai() -> ModuleType:
    module = ModuleType("openai")
    module.OpenAI = FakeOpenAI
    return module


class ScoringTests(TestCase):
    def setUp(self) -> None:
        self.settings = load_settings(Path(__file__).resolve().parents[1] / "config" / "settings.json")
        self.fake_module = install_fake_openai()

    def _make_scorer(self) -> OpenAIScorer:
        tempdir = self.enterContext(TemporaryDirectory())
        profile_path = Path(tempdir) / "resume.md"
        policy_path = Path(tempdir) / "scoring_policy.md"
        system_prompt_path = Path(tempdir) / "scoring_system.md"
        profile_path.write_text("candidate profile", encoding="utf-8")
        policy_path.write_text("generic scoring policy", encoding="utf-8")
        system_prompt_path.write_text("system prompt text", encoding="utf-8")
        with patch.dict(sys.modules, {"openai": self.fake_module}):
            return OpenAIScorer("test-key", "gpt-test", profile_path, policy_path, system_prompt_path)

    def test_parser_defaults_policy_path(self) -> None:
        args = build_parser().parse_args([])
        self.assertEqual(args.policy, "scoring_policy.md")

    def test_load_settings_reads_nested_scoring_config(self) -> None:
        self.assertEqual(self.settings.scoring.openai_model, "gpt-4o-mini")
        self.assertEqual(self.settings.scoring.digest_threshold, 70)
        self.assertEqual(self.settings.scoring.top_match_threshold, 82)
        self.assertEqual(self.settings.scoring.system_prompt_path, "prompts/scoring_system.md")
        self.assertEqual(self.settings.scoring.expected_verdicts, ["strong_match", "possible_match", "long_shot"])

    def test_loads_profile_and_policy_into_prompt(self) -> None:
        FakeOpenAI.next_message = SimpleNamespace(
            refusal=None,
            parsed=SimpleNamespace(
                model_dump=lambda: {
                    "fit_score": 82,
                    "verdict": "strong_match",
                    "matching_skills": ["React", "TypeScript"],
                    "gaps": ["No explicit Next.js mention"],
                    "seniority_alignment": "Aligned with a mid-level IC scope.",
                    "location_alignment": "Boston onsite role is compatible.",
                    "reason_to_apply": "Strong frontend overlap.",
                    "reason_to_skip": "Minor framework gap.",
                    "short_digest_summary": "Frontend product role with strong stack alignment.",
                }
            ),
        )
        scorer = self._make_scorer()

        result = scorer.score(make_job(), self.settings)

        self.assertEqual(FakeOpenAI.last_api_key, "test-key")
        self.assertEqual(result.fit_score, 82)
        self.assertEqual(result.verdict, "strong_match")
        parse_kwargs = FakeOpenAI.last_parse_kwargs
        self.assertIsNotNone(parse_kwargs)
        self.assertEqual(parse_kwargs["model"], "gpt-test")
        self.assertEqual(parse_kwargs["response_format"].__name__, "ScorePayload")
        messages = parse_kwargs["messages"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], "system prompt text")
        self.assertIn('"candidate_profile": "candidate profile"', messages[1]["content"])
        self.assertIn('"scoring_policy": "generic scoring policy"', messages[1]["content"])
        self.assertIn('"description": "Build React and TypeScript applications."', messages[1]["content"])
        self.assertIn('"expected_verdicts": ["strong_match", "possible_match", "long_shot"]', messages[1]["content"])

    def test_repo_scoring_instructions_include_local_and_experience_calibration(self) -> None:
        root = Path(__file__).resolve().parents[1]
        scoring_policy = (root / "scoring_policy.md").read_text(encoding="utf-8")
        system_prompt = (root / "prompts" / "scoring_system.md").read_text(encoding="utf-8")

        self.assertIn("Greater Boston locations named in the candidate profile", scoring_policy)
        self.assertIn("0 to 3 years of required experience are generally in bounds", scoring_policy)
        self.assertIn("2+ years should usually be treated as in bounds", scoring_policy)
        self.assertIn("Greater Boston locations named in the profile, including Cambridge", system_prompt)
        self.assertIn("0 to 3 years of required experience is in bounds", system_prompt)

    def test_raises_on_refusal(self) -> None:
        FakeOpenAI.next_message = SimpleNamespace(refusal="unsafe", parsed=None)
        scorer = self._make_scorer()

        with self.assertRaisesRegex(RuntimeError, "OpenAI refused to score job job-1: unsafe"):
            scorer.score(make_job(), self.settings)

    def test_raises_on_missing_parsed_payload(self) -> None:
        FakeOpenAI.next_message = SimpleNamespace(refusal=None, parsed=None)
        scorer = self._make_scorer()

        with self.assertRaisesRegex(RuntimeError, "OpenAI returned no parsed payload for job job-1"):
            scorer.score(make_job(), self.settings)
