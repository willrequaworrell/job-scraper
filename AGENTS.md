# AGENTS.md

## Project Intent

This repository is a pragmatic internal automation, not a product platform. Favor low moving-part count, explicit logging, config-driven behavior, and single-responsibility modules over abstraction for its own sake.

## Architecture Boundaries

- Keep v1 pure Python.
- Keep the pipeline linear and batch-oriented.
- Treat `config/settings.json` as the default source for tuneable behavior.
- Treat `resume.md` as the single candidate-profile input for scoring.
- Treat `data/job_digest.sqlite` as the durable state source used for dedupe and resurfacing.

## Implementation Expectations

- Normalize external job records into one internal schema immediately.
- Apply cheap deterministic filters before any LLM call.
- Use OpenAI structured outputs for scoring; do not parse freeform prose.
- Attach explicit reason labels to filtered-out jobs.
- Fail loudly on fetch, scoring, and delivery errors.
- Avoid committing secrets or adding external services unless explicitly requested.

## Operational Expectations

- GitHub Actions is the production scheduler.
- Successful scheduled runs may commit the updated SQLite database back to `main`.
- Empty-result runs still send a short confirmation email by default.

## Testing Expectations

- Cover normalization, rule filtering, dedupe/resurfacing, and digest rendering with local tests.
- Keep integration points thin and import external SDKs lazily so unit tests do not need network-bound dependencies.
