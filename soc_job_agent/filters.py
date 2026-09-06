"""Deterministic, zero-cost filtering applied before any Gemini call.

Two passes, matching what data is available at each stage:
  - pre_filter(): title/location/freshness/dedup, using only the cheap
    search-result-card fields (no per-job network request yet).
  - post_detail_filter(): seniority + years-of-experience exclusion, using
    the detail page fetched only for survivors of pre_filter().
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta

from .linkedin_search import JobListing

logger = logging.getLogger("soc_job_agent.filters")

LOCATION_KEYWORDS = ["pune", "mumbai", "thane", "navi mumbai"]

TITLE_INCLUDE_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"\bsoc\b",
        r"security\s+operations",
        r"cyber\s+(defense|defence|security)\s+analyst",
        r"\bsecurity\s+analyst\b",
        r"incident\s+response\s+analyst",
        r"threat\s+(detection|hunting)\s+analyst",
        r"cyber\s*security\s+operations",
        r"cyber\s+incident",
    ]
]

TITLE_EXCLUDE_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"\bsr\.?\b",
        r"\bsenior\b",
        r"\blead\b",
        r"\bmanager\b",
        r"\bhead\b",
        r"\bprincipal\b",
        r"\barchitect\b",
        r"\bdirector\b",
        r"\bvp\b",
        r"\bvice\s+president\b",
        r"\bchief\b",
        r"\bstaff\b",
        r"\bconsultant\s+iii\b",
        r"\bii\b",
        r"\biii\b",
        r"\biv\b",
        r"\bl\s*[2-9]\b",
        r"\blevel\s*[2-9]\b",
        r"\btier\s*[2-9]\b",
    ]
]

EXCLUDED_SENIORITY = {"mid-senior level", "director", "executive"}

# Matches "3-5 years", "5+ years", "3 to 5 years", "minimum 3 years", etc.
YEARS_RE = re.compile(
    r"(\d+)\s*\+?\s*(?:to|-|–)\s*(\d+)?\s*\+?\s*years?|(\d+)\s*\+\s*years?",
    re.I,
)

FRESH_DAYS = 3
MAX_AGE_DAYS = 21


def _normalize_key(job: JobListing) -> str:
    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", s.lower())

    return f"{norm(job.company)}|{norm(job.title)}"


def title_is_relevant(title: str) -> bool:
    if any(p.search(title) for p in TITLE_EXCLUDE_PATTERNS):
        return False
    return any(p.search(title) for p in TITLE_INCLUDE_PATTERNS)


def location_is_relevant(location: str) -> bool:
    loc = location.lower()
    return any(k in loc for k in LOCATION_KEYWORDS)


def min_years_required(text: str) -> int | None:
    """Best-effort extraction of the minimum years of experience mentioned.

    Returns None when no explicit figure is found (caller should not treat
    that as disqualifying -- absence of a number is not evidence of
    seniority).
    """
    matches = YEARS_RE.findall(text)
    mins = []
    for m in matches:
        lo_range, _hi_range, lo_plus = m
        if lo_range:
            mins.append(int(lo_range))
        elif lo_plus:
            mins.append(int(lo_plus))
    return min(mins) if mins else None


def pre_filter(jobs: list[JobListing], today: date | None = None) -> list[JobListing]:
    today = today or date.today()
    cutoff = today - timedelta(days=MAX_AGE_DAYS)

    stage_location = [j for j in jobs if location_is_relevant(j.location)]
    logger.info("After location filter: %d/%d", len(stage_location), len(jobs))

    stage_title = [j for j in stage_location if title_is_relevant(j.title)]
    logger.info("After title filter: %d/%d", len(stage_title), len(stage_location))

    stage_fresh = [
        j for j in stage_title if j.posted_date is None or j.posted_date >= cutoff
    ]
    logger.info("After freshness filter (<=%dd): %d/%d", MAX_AGE_DAYS, len(stage_fresh), len(stage_title))

    # Dedup by normalized (company, title): keep the most recent posting.
    best_by_key: dict[str, JobListing] = {}
    for job in stage_fresh:
        key = _normalize_key(job)
        existing = best_by_key.get(key)
        if existing is None:
            best_by_key[key] = job
            continue
        existing_date = existing.posted_date or date.min
        job_date = job.posted_date or date.min
        if job_date > existing_date:
            best_by_key[key] = job

    deduped = list(best_by_key.values())
    logger.info("After dedup: %d/%d", len(deduped), len(stage_fresh))

    deduped.sort(key=lambda j: j.posted_date or date.min, reverse=True)
    return deduped


def post_detail_filter(jobs: list[JobListing]) -> list[JobListing]:
    survivors = []
    for job in jobs:
        if job.seniority and job.seniority.lower() in EXCLUDED_SENIORITY:
            logger.info("Excluding %s (%s): seniority=%s", job.title, job.company, job.seniority)
            continue

        combined_text = f"{job.title} {job.description_snippet}"
        required_years = min_years_required(combined_text)
        if required_years is not None and required_years > 1:
            logger.info(
                "Excluding %s (%s): requires >=%d years", job.title, job.company, required_years
            )
            continue

        survivors.append(job)

    logger.info("After seniority/experience filter: %d/%d", len(survivors), len(jobs))
    return survivors


def is_recent(job: JobListing, today: date | None = None) -> bool:
    today = today or date.today()
    return job.posted_date is not None and (today - job.posted_date).days <= FRESH_DAYS
