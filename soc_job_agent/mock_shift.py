"""Daily mock SOC ticket: a generated alert scenario + model triage answer.

Self-graded by design (no reply-parsing/webhook infrastructure): the email
includes both the scenario and the model answer/rubric in the same message,
so you write your own triage response first, then scroll down to check
yourself against a MITRE ATT&CK-referenced rubric.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from . import http_utils
from .config import Config
from .gemini_client import GeminiError, MODEL, API_URL

logger = logging.getLogger("soc_job_agent.mock_shift")

HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "mock_shift_history.json"
LOOKBACK_FOR_REPEAT_AVOIDANCE = 5

SCENARIO_TYPES = [
    "phishing email reported by an employee",
    "malware beacon / C2 communication detected by EDR",
    "brute-force login attempts against a public-facing service",
    "suspicious PowerShell execution on an endpoint",
    "possible data exfiltration alert (large outbound transfer)",
    "insider threat indicator (unusual access pattern)",
    "ransomware precursor activity (mass file renaming attempts)",
    "DNS tunneling / anomalous DNS query volume",
    "impossible-travel / MFA fatigue alert",
    "suspicious USB / removable media activity",
]

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "scenario_title": {"type": "STRING"},
        "alert_details": {"type": "STRING"},
        "your_task": {"type": "STRING"},
        "model_answer": {"type": "STRING"},
        "mitre_attack_refs": {"type": "STRING"},
        "grading_checklist": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
    },
    "required": ["scenario_title", "alert_details", "your_task", "model_answer", "mitre_attack_refs", "grading_checklist"],
}

PROMPT_TEMPLATE = """You are training a fresher SOC (Security Operations Center) Analyst \
with a realistic daily practice ticket.

Scenario type for today: {scenario_type}

Generate a single realistic SOC alert/ticket scenario of this type, as if pulled from a \
real SIEM, including plausible but fictional details (IPs, usernames, hostnames, \
timestamps, process names as appropriate). Then write the ideal Tier-1/Tier-2 triage \
response a strong fresher analyst should produce, and a short grading checklist.

Respond with JSON only, matching the schema:
- scenario_title: short title
- alert_details: the raw-ish alert/ticket text a SOC analyst would actually see (with \
fictional IOCs/timestamps/hostnames), 100-200 words
- your_task: 1-2 sentences telling the analyst what to do with this ticket
- model_answer: the ideal step-by-step triage/response (investigation steps, \
verdict, and recommended action), 150-250 words
- mitre_attack_refs: relevant MITRE ATT&CK technique ID(s) and name(s), e.g. "T1566 \
Phishing"
- grading_checklist: 4-6 short bullet points a learner can self-check their own answer \
against
"""


def _load_history() -> list[str]:
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        return data.get("recent_types", [])
    except (json.JSONDecodeError, OSError):
        return []


def _save_history(recent_types: list[str]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps({"recent_types": recent_types}, indent=2), encoding="utf-8")


def _pick_scenario_type() -> str:
    recent = _load_history()
    avoid = set(recent[-LOOKBACK_FOR_REPEAT_AVOIDANCE:])
    candidates = [t for t in SCENARIO_TYPES if t not in avoid] or SCENARIO_TYPES
    return candidates[0]


def _record_used(scenario_type: str) -> None:
    recent = _load_history()
    recent.append(scenario_type)
    _save_history(recent[-(LOOKBACK_FOR_REPEAT_AVOIDANCE * 2):])


def generate(api_key: str, today: date | None = None) -> dict | None:
    scenario_type = _pick_scenario_type()
    prompt = PROMPT_TEMPLATE.format(scenario_type=scenario_type)

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "temperature": 0.8,
        },
    }
    url = API_URL.format(model=MODEL, key=api_key)
    try:
        status, raw = http_utils.request(
            url,
            method="POST",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            timeout=60,
            max_attempts=4,
            backoff_seconds=4.0,
        )
        if status != 200:
            raise GeminiError(f"Gemini API returned HTTP {status}: {raw[:300]!r}")
        payload = json.loads(raw)
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        scenario = json.loads(text)
    except Exception as exc:
        logger.error("Mock shift generation failed: %s", exc)
        return None

    _record_used(scenario_type)
    return scenario


def build_section_html(scenario: dict | None) -> str:
    if scenario is None:
        return """
        <h3 style="margin-bottom:4px;">Today's Mock SOC Ticket</h3>
        <p style="color:#666;">Unavailable today (generation failed) -- try again tomorrow.</p>
        """

    checklist_items = "".join(f"<li>{item}</li>" for item in scenario.get("grading_checklist", []))

    return f"""
    <h3 style="margin-bottom:4px;">Today's Mock SOC Ticket: {scenario.get('scenario_title', '')}</h3>
    <p style="background:#fafafa;border:1px solid #ddd;padding:10px;white-space:pre-wrap;">{scenario.get('alert_details', '')}</p>
    <p><strong>Your task:</strong> {scenario.get('your_task', '')}</p>
    <p style="color:#888;font-size:12px;">Write your own triage response on paper first --
    email clients don't support click-to-reveal, so the model answer is directly below.
    No peeking until you've written yours.</p>
    <p style="margin-bottom:2px;"><strong>--- Model answer below ---</strong></p>
    <p><strong>MITRE ATT&amp;CK:</strong> {scenario.get('mitre_attack_refs', '')}</p>
    <p style="white-space:pre-wrap;">{scenario.get('model_answer', '')}</p>
    <p><strong>Self-check against:</strong></p>
    <ul>{checklist_items}</ul>
    """
