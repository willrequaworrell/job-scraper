from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_digest.config import load_runtime_env


class RuntimeEnvTests(TestCase):
    def test_load_runtime_env_defaults_optional_flags_to_false(self) -> None:
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "openai", "RESEND_API_KEY": "resend", "EMAIL_TO": "test@example.com"},
            clear=True,
        ):
            runtime = load_runtime_env()

        self.assertFalse(runtime.disable_resurface_suppression)
        self.assertIsNone(runtime.debug_output_path)

    def test_load_runtime_env_reads_optional_flags(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "openai",
                "RESEND_API_KEY": "resend",
                "EMAIL_TO": "test@example.com",
                "JOB_DIGEST_DISABLE_RESURFACE_SUPPRESSION": "true",
                "JOB_DIGEST_DEBUG_OUTPUT_PATH": "artifacts/last_run.json",
            },
            clear=True,
        ):
            runtime = load_runtime_env()

        self.assertTrue(runtime.disable_resurface_suppression)
        self.assertEqual(runtime.debug_output_path, "artifacts/last_run.json")
