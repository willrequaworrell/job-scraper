from __future__ import annotations

import logging

from job_digest.config import Settings

logger = logging.getLogger(__name__)


def fetch_jobs(settings: Settings) -> list[dict]:
    try:
        from jobspy import scrape_jobs
    except ImportError as exc:
        raise RuntimeError("python-jobspy is required to fetch jobs. Install project dependencies first.") from exc

    rows: list[dict] = []
    for search_term in settings.search_terms:
        logger.info("Fetching jobs for search term: %s", search_term)
        dataframe = scrape_jobs(
            site_name=settings.sites,
            search_term=search_term,
            google_search_term=f"{search_term} jobs in {settings.google_search_location}",
            location=settings.google_search_location,
            results_wanted=settings.results_per_search,
            hours_old=settings.hours_old,
            country_indeed=settings.country_indeed,
        )
        if dataframe is None:
            continue
        rows.extend(dataframe.fillna("").to_dict("records"))
    return rows
