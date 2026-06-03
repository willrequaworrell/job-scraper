# Job Digest Automation

Job Digest Automation is a private, Python-first batch workflow that fetches software jobs, removes obvious weak fits, scores plausible matches against a curated candidate profile, and emails a compact digest of the strongest opportunities.

## V1 Goal

Answer one question well: which newly posted jobs are plausibly worth applying to based on the candidate's actual background?

V1 is intentionally narrow:

- One ingestion layer: `python-jobspy`
- One scoring path: OpenAI structured outputs
- One delivery path: Resend
- One scheduler: GitHub Actions
- One persistence layer: tracked SQLite state

## Non-Goals

- LinkedIn-specific scraping
- Multi-provider ranking ensembles
- Embedding-based pre-ranking
- Auto-apply or browser automation
- Dashboard UI, Notion integration, or analytics surface

## Repository Shape

- `src/job_digest/`: pipeline code
- `config/settings.json`: committed runtime policy
- `resume.md`: curated candidate profile for scoring
- `data/job_digest.sqlite`: tracked dedupe/history state
- `.github/workflows/job-digest.yml`: scheduled execution

## Required Environment Variables

- `OPENAI_API_KEY`
- `RESEND_API_KEY`
- `EMAIL_TO`

Copy `.env.example` to `.env` for local development.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m unittest discover -s tests -v
python -m job_digest --dry-run
```

`--dry-run` exercises fetch, normalize, filter, and score logic without sending email or mutating the SQLite state.

Optional dev-only environment flags:

- `JOB_DIGEST_DISABLE_RESURFACE_SUPPRESSION=1` ignores the SQLite resurfacing cooldown and re-scores jobs even if they were surfaced recently.
- `JOB_DIGEST_DEBUG_OUTPUT_PATH=artifacts/last_run.json` writes a JSON artifact containing every unique normalized job and its final pipeline outcome for the run.

## Runtime Behavior

The pipeline runs in this order:

1. Load config and environment.
2. Fetch recent jobs from JobSpy.
3. Normalize every raw job into one internal shape.
4. Update last-seen timestamps and suppress jobs still inside the resurfacing cooldown.
5. Apply deterministic rule filters with explicit rejection reasons.
6. Score survivors with OpenAI structured outputs.
7. Keep only jobs at or above the configured threshold.
8. Render an HTML digest.
9. Send via Resend.
10. Persist run metadata and job state.

The workflow sends a short "no strong matches this run" email by default when nothing passes threshold. Jobs that were surfaced previously can reappear after a seven-day cooldown and are re-scored when they do.
