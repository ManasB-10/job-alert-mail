"""Rolling corpus of job descriptions seen by the pipeline.

Feeds skill_gap.py and linkedin_coach.py: both need a window of recent real
job-description text to derive "what's actually in demand" rather than
generic advice. Stored as JSONL (one job per line) so appending is O(1) and
doesn't require rewriting the whole file each run.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

from .linkedin_search import JobListing

logger = logging.getLogger("soc_job_agent.corpus")

CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "job_corpus.jsonl"
RETENTION_DAYS = 90


def append(jobs: list[JobListing], today: date) -> None:
    if not jobs:
        return
    CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CORPUS_PATH.open("a", encoding="utf-8") as f:
        for job in jobs:
            record = {
                "seen_date": today.isoformat(),
                "job_id": job.job_id,
                "title": job.title,
                "company": job.company,
                "description_snippet": job.description_snippet,
            }
            f.write(json.dumps(record) + "\n")
    logger.info("Appended %d job(s) to corpus (%s)", len(jobs), CORPUS_PATH)


def load_recent(days: int = RETENTION_DAYS) -> list[dict]:
    if not CORPUS_PATH.exists():
        return []
    cutoff = date.today() - timedelta(days=days)
    records = []
    with CORPUS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                seen_date = date.fromisoformat(record.get("seen_date", ""))
            except ValueError:
                continue
            if seen_date >= cutoff:
                records.append(record)
    return records


def prune(days: int = RETENTION_DAYS) -> None:
    """Rewrites the corpus keeping only the last `days` of entries.

    Cheap to call once a day; keeps the file from growing unbounded.
    """
    records = load_recent(days=days)
    if not CORPUS_PATH.exists():
        return
    tmp_path = CORPUS_PATH.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    tmp_path.replace(CORPUS_PATH)
