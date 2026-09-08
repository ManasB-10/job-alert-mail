"""Orchestrates one end-to-end run of the daily SOC Analyst career digest.

Beyond the job listings, this bundles several independent "career coaching"
agents into the same email: skill-gap analysis, a mock SOC ticket, interview
drill questions, resume tailoring, LinkedIn keyword gaps, and application
follow-up reminders. Each is wrapped in its own try/except -- a failure in
one section (e.g. Gemini down for the mock-shift generator) never blocks the
others or the core job email.
"""

from __future__ import annotations

import logging
from datetime import date

from . import (
    application_tracker,
    corpus,
    emailer,
    gemini_client,
    history,
    interview_drill,
    linkedin_coach,
    linkedin_search,
    mock_shift,
    report_store,
    resume_coach,
    skill_gap,
)
from .config import Config
from .filters import post_detail_filter, pre_filter

logger = logging.getLogger("soc_job_agent.pipeline")

MAX_DETAIL_FETCHES = 30  # bounds cost/time of the enrichment step


def _safe(label: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        logger.exception("Section %r failed -- continuing without it", label)
        return None


def run(config: Config, today: date | None = None) -> dict:
    today = today or date.today()
    logger.info("=== Starting SOC Analyst career digest run for %s ===", today.isoformat())

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

    _safe("corpus.append", corpus.append, detail_filtered, today)
    _safe("corpus.prune", corpus.prune)

    unreported = history.filter_unreported(detail_filtered, today=today)
    ranked_jobs, reasons, summary = gemini_client.score_and_rank(unreported, config.gemini_api_key)

    result = {
        "date": today.isoformat(),
        "raw_count": len(raw_jobs),
        "rule_filtered_count": len(rule_filtered),
        "detail_filtered_count": len(detail_filtered),
        "unreported_count": len(unreported),
        "sent_count": len(ranked_jobs),
    }

    # --- Career coaching sections (each independently fault-tolerant) ---
    corpus_records = _safe("corpus.load_recent", corpus.load_recent) or []

    skill_gap_html = _safe("skill_gap", skill_gap.build_section_html, corpus_records) or ""

    scenario = _safe("mock_shift.generate", mock_shift.generate, config.gemini_api_key, today)
    mock_shift_html = _safe("mock_shift.build_section_html", mock_shift.build_section_html, scenario) or ""

    daily_questions = _safe("interview_drill.pick", interview_drill.pick_daily_questions) or []
    interview_html = _safe("interview_drill.build_section_html", interview_drill.build_section_html, daily_questions) or ""
    if daily_questions:
        _safe("interview_drill.record_sent", interview_drill.record_sent, daily_questions, today)

    top_job_for_resume = ranked_jobs[0] if ranked_jobs else (detail_filtered[0] if detail_filtered else None)
    resume_result = None
    if top_job_for_resume is not None:
        resume_result = _safe("resume_coach.analyze", resume_coach.analyze, top_job_for_resume, config.gemini_api_key)
    resume_html = _safe("resume_coach.build_section_html", resume_coach.build_section_html, top_job_for_resume, resume_result) or ""

    linkedin_gap = _safe("linkedin_coach.find_gaps", linkedin_coach.find_gaps, corpus_records)
    linkedin_html = _safe("linkedin_coach.build_section_html", linkedin_coach.build_section_html, linkedin_gap) or ""

    reminders = _safe("application_tracker.build_reminders", application_tracker.build_reminders, today) or []
    tracker_html = _safe("application_tracker.build_section_html", application_tracker.build_section_html, reminders) or ""

    extra_sections = [skill_gap_html, mock_shift_html, interview_html, resume_html, linkedin_html, tracker_html]

    subject = f"Daily SOC Analyst Fresher Jobs – Pune & Mumbai – {today.strftime('%d %b %Y')}"
    html_body = emailer.build_email_html(ranked_jobs, reasons, summary, today, extra_sections=extra_sections)

    # Archive before sending: a saved report survives even if SMTP fails.
    _safe("report_store.upload_daily_report", report_store.upload_daily_report,
          config, today, html_body, ranked_jobs, reasons, summary, result)

    emailer.send_email(config, subject, html_body)

    if ranked_jobs:
        history.record_sent(ranked_jobs, today=today)

    logger.info("=== Run complete: %s ===", result)
    return result
