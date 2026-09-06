"""No-API-key job sourcing via LinkedIn's public "guest" job search pages.

This uses the same public HTML endpoints LinkedIn serves to logged-out
visitors and search engines (no auth, no official API, no key required).
It is intentionally the ONLY network "search" source: Gemini is used
downstream purely for judgment (scoring/dedup/summarization), per the
project's cost-efficiency goal and because Gemini's Google Search grounding
tool requires a billed project and is not available on this key.

Being an unofficial endpoint, its HTML structure can change; all parsing is
regex-based and defensive (missing fields are tolerated, not fatal).
"""

from __future__ import annotations

import html
import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import date, datetime

from . import http_utils

logger = logging.getLogger("soc_job_agent.linkedin")

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

KEYWORDS = [
    "SOC Analyst",
    "Cyber Security Analyst",
    "Security Operations Analyst",
]

LOCATIONS = [
    "Pune, Maharashtra, India",
    "Mumbai, Maharashtra, India",
    "Navi Mumbai, Maharashtra, India",
    "Thane, Maharashtra, India",
]

# Past 30 days at the source; Python-side rule filtering does the real
# freshness prioritization (preferring <=3 days, see filters.py).
TIME_POSTED_FILTER = "r2592000"

JOB_ID_RE = re.compile(r"-(\d+)(?:\?|$)")
CARD_SPLIT_MARKER = "base-card relative"
TITLE_RE = re.compile(r'base-search-card__title">\s*([^<]+?)\s*</h3', re.S)
COMPANY_RE = re.compile(r'base-search-card__subtitle">.*?>\s*([^<]+?)\s*</a', re.S)
LOCATION_RE = re.compile(r'job-search-card__location">\s*([^<]+?)\s*</span', re.S)
LINK_RE = re.compile(r'href="([^"]+)"')
DATE_RE = re.compile(r'datetime="([^"]+)"')

CRITERIA_RE = re.compile(r"description__job-criteria-text[^>]*>\s*([^<]+)", re.S)
DESCRIPTION_RE = re.compile(r'show-more-less-html__markup[^>]*>(.*?)</div>', re.S)
TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class JobListing:
    job_id: str
    title: str
    company: str
    location: str
    url: str
    posted_date: date | None
    query_keyword: str
    seniority: str | None = None
    description_snippet: str = ""
    source: str = "LinkedIn"


def _clean(text: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def _extract_job_id(url: str) -> str | None:
    path = url.split("?", 1)[0]
    match = JOB_ID_RE.search(path)
    return match.group(1) if match else None


def _parse_cards(raw_html: str, keyword: str) -> list[JobListing]:
    listings: list[JobListing] = []
    cards = raw_html.split(CARD_SPLIT_MARKER)[1:]
    for card in cards:
        link_match = LINK_RE.search(card)
        if not link_match:
            continue
        url = link_match.group(1).split("&", 1)[0] if "&" in link_match.group(1) else link_match.group(1)
        # keep it unescaped/clean and drop tracking query params entirely
        url = html.unescape(url).split("?", 1)[0]
        job_id = _extract_job_id(url)
        if not job_id:
            continue

        title_match = TITLE_RE.search(card)
        company_match = COMPANY_RE.search(card)
        location_match = LOCATION_RE.search(card)
        date_match = DATE_RE.search(card)

        posted_date = None
        if date_match:
            try:
                posted_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
            except ValueError:
                posted_date = None

        listings.append(
            JobListing(
                job_id=job_id,
                title=_clean(title_match.group(1)) if title_match else "(unknown title)",
                company=_clean(company_match.group(1)) if company_match else "(unknown company)",
                location=_clean(location_match.group(1)) if location_match else "",
                url=url,
                posted_date=posted_date,
                query_keyword=keyword,
            )
        )
    return listings


def search_all(max_pages_per_query: int = 1, page_size: int = 25) -> list[JobListing]:
    """Runs the keyword x location grid against LinkedIn's guest search API.

    Returns raw, deduplicated-by-job-id listings with no relevance filtering
    applied yet -- that happens in filters.py.
    """
    seen: dict[str, JobListing] = {}

    for keyword in KEYWORDS:
        for location in LOCATIONS:
            for page in range(max_pages_per_query):
                params = {
                    "keywords": keyword,
                    "location": location,
                    "f_TPR": TIME_POSTED_FILTER,
                    "start": str(page * page_size),
                }
                url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"
                try:
                    status, body = http_utils.request(url, timeout=20, max_attempts=3)
                except Exception as exc:
                    logger.error("Search request failed for %r/%r: %s", keyword, location, exc)
                    continue

                if status != 200:
                    logger.warning(
                        "Search returned HTTP %s for keyword=%r location=%r", status, keyword, location
                    )
                    continue

                raw_html = body.decode("utf-8", errors="replace")
                listings = _parse_cards(raw_html, keyword)
                logger.info(
                    "Search keyword=%r location=%r page=%d -> %d listings",
                    keyword, location, page, len(listings),
                )
                if not listings:
                    break  # no more pages for this combo

                for job in listings:
                    if job.job_id not in seen:
                        seen[job.job_id] = job

    logger.info("Total unique raw listings across all queries: %d", len(seen))
    return list(seen.values())


def enrich_with_details(jobs: list[JobListing]) -> None:
    """Fetches each job's detail page in-place to add seniority + description.

    Only called on the already rule-filtered shortlist to keep request
    volume low (see pipeline.py).
    """
    for job in jobs:
        try:
            status, body = http_utils.request(job.url, timeout=20, max_attempts=2)
        except Exception as exc:
            logger.warning("Detail fetch failed for %s: %s", job.url, exc)
            continue

        if status != 200:
            logger.warning("Detail fetch HTTP %s for %s", status, job.url)
            continue

        raw_html = body.decode("utf-8", errors="replace")

        criteria = CRITERIA_RE.findall(raw_html)
        if criteria:
            job.seniority = _clean(criteria[0])

        desc_match = DESCRIPTION_RE.search(raw_html)
        if desc_match:
            text = TAG_RE.sub(" ", desc_match.group(1))
            job.description_snippet = _clean(text)[:600]
