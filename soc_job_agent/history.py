"""Local JSON history of previously-emailed jobs, to avoid repeat reports.

A job is skipped if it was already sent within RESEND_COOLDOWN_DAYS, unless
its title or company text changed since then (treated as a materially
different posting, e.g. a reposted/updated role).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path

from .linkedin_search import JobListing

logger = logging.getLogger("soc_job_agent.history")

HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "seen_jobs.json"
RESEND_COOLDOWN_DAYS = 30


def _load() -> dict:
    if not HISTORY_PATH.exists():
        return {}
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read history file %s (%s) -- starting fresh", HISTORY_PATH, exc)
        return {}


def load_all() -> dict:
    """Public accessor: {job_id: {title, company, fingerprint, last_sent}}."""
    return _load()


def _save(data: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = HISTORY_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(HISTORY_PATH)


def _fingerprint(job: JobListing) -> str:
    return f"{job.title.strip().lower()}|{job.company.strip().lower()}"


def filter_unreported(jobs: list[JobListing], today: date | None = None) -> list[JobListing]:
    today = today or date.today()
    history = _load()
    cutoff = today - timedelta(days=RESEND_COOLDOWN_DAYS)

    fresh: list[JobListing] = []
    for job in jobs:
        entry = history.get(job.job_id)
        if entry is None:
            fresh.append(job)
            continue

        last_sent = datetime.strptime(entry["last_sent"], "%Y-%m-%d").date()
        if last_sent < cutoff:
            fresh.append(job)
            continue

        if entry.get("fingerprint") != _fingerprint(job):
            logger.info("Job %s changed since last send -- treating as new", job.job_id)
            fresh.append(job)
            continue

        logger.debug("Skipping already-reported job %s (%s)", job.job_id, job.title)

    logger.info("After history dedup: %d/%d", len(fresh), len(jobs))
    return fresh


def record_sent(jobs: list[JobListing], today: date | None = None) -> None:
    today = today or date.today()
    history = _load()
    for job in jobs:
        history[job.job_id] = {
            "title": job.title,
            "company": job.company,
            "fingerprint": _fingerprint(job),
            "last_sent": today.strftime("%Y-%m-%d"),
        }
    _save(history)
    logger.info("Recorded %d job(s) in history (%s)", len(jobs), HISTORY_PATH)
