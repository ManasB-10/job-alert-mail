"""Daily spaced-repetition selection over the interview question bank."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .interview_bank import QUESTIONS

logger = logging.getLogger("soc_job_agent.interview_drill")

HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "interview_drill_history.json"
QUESTIONS_PER_DAY = 3


def _question_key(q: dict) -> str:
    return q["question"]


def _load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {}
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_history(history: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")


def pick_daily_questions(count: int = QUESTIONS_PER_DAY) -> list[dict]:
    history = _load_history()

    def sort_key(q: dict):
        entry = history.get(_question_key(q), {"times_sent": 0, "last_sent": ""})
        return (entry["times_sent"], entry["last_sent"])

    ranked = sorted(QUESTIONS, key=sort_key)
    return ranked[:count]


def record_sent(questions: list[dict], today) -> None:
    history = _load_history()
    for q in questions:
        key = _question_key(q)
        entry = history.get(key, {"times_sent": 0, "last_sent": ""})
        entry["times_sent"] = entry.get("times_sent", 0) + 1
        entry["last_sent"] = today.isoformat()
        history[key] = entry
    _save_history(history)


def build_section_html(questions: list[dict]) -> str:
    if not questions:
        return ""

    items = []
    for q in questions:
        items.append(f"""
        <div style="margin-bottom:10px;">
          <p style="margin:0;"><strong>[{q['category']}]</strong> {q['question']}</p>
          <p style="margin:2px 0 0 0;color:#555;">{q['answer']}</p>
        </div>
        """)

    return f"""
    <h3 style="margin-bottom:4px;">Interview Drill (today's {len(questions)})</h3>
    {''.join(items)}
    """
