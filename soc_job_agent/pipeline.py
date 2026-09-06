"""Orchestrates one end-to-end run of the daily job digest."""

from __future__ import annotations

import logging
from datetime import date

from . import emailer, gemini_client, history, linkedin_search
from .config import Config
from .filters import post_detail_filter, pre_filter

logger = logging.getLogger("soc_job_agent.pipeline")

MAX_DETAIL_FETCHES = 30  # bounds cost/time of the enrichment step


def run(config: Config, today: date | None = None) -> dict:
    today = today or date.today()
    logger.info("=== Starting SOC Analyst job digest run for %s ===", today.isoformat())

    raw_jobs = linkedin_search.search_all()
    if not raw_jobs:
        logger.warning("No raw listings retrieved from LinkedIn search -- check connectivity/HTML format")

    rule_filtered = pre_filter(raw_jobs, today=today)
    shortlist = rule_filtered[:MAX_DETAIL_FETCHES]
    if len(rule_filtered) > MAX_DETAIL_FETCHES:
        logger.info(
            "Capping detail enrichment to top %d of %d rule-filtered candidates",
            MAX_DETAIL_FETCHES, len(rule_filtered),
        )

    linkedin_search.enrich_with_details(shortlist)
    detail_filtered = post_detail_filter(shortlist)

    unreported = history.filter_unreported(detail_filtered, today=today)

    ranked_jobs, reasons, summary = gemini_client.score_and_rank(unreported, config.gemini_api_key)

    subject = f"Daily SOC Analyst Fresher Jobs – Pune & Mumbai – {today.strftime('%d %b %Y')}"
    html_body = emailer.build_email_html(ranked_jobs, reasons, summary, today)
    emailer.send_email(config, subject, html_body)

    if ranked_jobs:
        history.record_sent(ranked_jobs, today=today)

    result = {
        "date": today.isoformat(),
        "raw_count": len(raw_jobs),
        "rule_filtered_count": len(rule_filtered),
        "detail_filtered_count": len(detail_filtered),
        "unreported_count": len(unreported),
        "sent_count": len(ranked_jobs),
    }
    logger.info("=== Run complete: %s ===", result)
    return result
