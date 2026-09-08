"""Application tracking: applied/status/follow-up reminders.

No inbound email channel exists (would need a webhook + public endpoint,
out of scope), so tracking is a local JSON file you update yourself via the
track.py CLI at the project root. This module just reads it to cross-
reference against job history for follow-up reminders and "you haven't
applied to this recent match yet" nudges.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

from . import history as history_module

logger = logging.getLogger("soc_job_agent.application_tracker")

APPLICATIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "applications.json"

FOLLOWUP_CHECKPOINTS_DAYS = (7, 14, 21)
NUDGE_WINDOW_DAYS = 5
STOP_REMINDING_AFTER_DAYS = 28


def load_applications() -> dict:
    if not APPLICATIONS_PATH.exists():
        return {}
    try:
        return json.loads(APPLICATIONS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read %s (%s) -- treating as empty", APPLICATIONS_PATH, exc)
        return {}


def save_applications(data: dict) -> None:
    APPLICATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = APPLICATIONS_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(APPLICATIONS_PATH)


def mark_applied(job_id: str, title: str = "", company: str = "", notes: str = "", today: date | None = None) -> None:
    today = today or date.today()
    data = load_applications()
    data[job_id] = {
        "title": title or data.get(job_id, {}).get("title", ""),
        "company": company or data.get(job_id, {}).get("company", ""),
        "applied_date": today.isoformat(),
        "status": "applied",
        "notes": notes,
    }
    save_applications(data)


def update_status(job_id: str, status: str, notes: str = "") -> bool:
    data = load_applications()
    if job_id not in data:
        return False
    data[job_id]["status"] = status
    if notes:
        data[job_id]["notes"] = notes
    save_applications(data)
    return True


def _job_history() -> dict:
    return history_module.load_all()


def build_reminders(today: date | None = None) -> list[str]:
    today = today or date.today()
    applications = load_applications()
    job_hist = _job_history()
    reminders: list[str] = []

    for job_id, app in applications.items():
        if app.get("status") != "applied":
            continue
        try:
            applied_date = datetime.strptime(app["applied_date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        days_since = (today - applied_date).days
        if days_since > STOP_REMINDING_AFTER_DAYS:
            continue
        if days_since in FOLLOWUP_CHECKPOINTS_DAYS:
            reminders.append(
                f"Follow up on {app.get('title', 'this role')} @ {app.get('company', 'unknown')} "
                f"-- applied {days_since} days ago, no status update yet."
            )

    applied_ids = set(applications.keys())
    for job_id, entry in job_hist.items():
        if job_id in applied_ids:
            continue
        try:
            last_sent = datetime.strptime(entry["last_sent"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        if (today - last_sent).days <= NUDGE_WINDOW_DAYS:
            reminders.append(
                f"You haven't marked {entry.get('title', 'this role')} @ "
                f"{entry.get('company', 'unknown')} (sent {(today - last_sent).days}d ago) as applied yet -- "
                f"run: python track.py apply {job_id}"
            )

    return reminders


MAX_REMINDERS_SHOWN = 8


def build_section_html(reminders: list[str]) -> str:
    if not reminders:
        return """
        <h3 style="margin-bottom:4px;">Application Tracker</h3>
        <p style="color:#666;">No pending follow-ups or nudges today. Mark jobs as
        applied with <code>python track.py apply &lt;job_id&gt;</code> (job_id is the
        number at the end of each listing's LinkedIn URL) to start tracking.</p>
        """

    shown = reminders[:MAX_REMINDERS_SHOWN]
    remainder = len(reminders) - len(shown)
    items = "".join(f"<li>{r}</li>" for r in shown)
    more_note = f"<p style='color:#888;'>+ {remainder} more -- see <code>python track.py list</code>.</p>" if remainder > 0 else ""
    return f"""
    <h3 style="margin-bottom:4px;">Application Tracker</h3>
    <ul>{items}</ul>
    {more_note}
    """
