"""Resume/ATS tailoring suggestions against today's top-matched job.

Needs your actual resume text, which nobody but you has -- reads it from
data/resume.txt. Until that file exists, the section explains how to enable
itself instead of silently doing nothing.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from . import http_utils
from .gemini_client import GeminiError, MODEL, API_URL
from .linkedin_search import JobListing

logger = logging.getLogger("soc_job_agent.resume_coach")

RESUME_PATH = Path(__file__).resolve().parent.parent / "data" / "resume.txt"
MAX_RESUME_CHARS = 6000

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "matching_strengths": {"type": "ARRAY", "items": {"type": "STRING"}},
        "keyword_gaps": {"type": "ARRAY", "items": {"type": "STRING"}},
        "phrasing_suggestions": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["matching_strengths", "keyword_gaps", "phrasing_suggestions"],
}

PROMPT_TEMPLATE = """You are an ATS (Applicant Tracking System) resume coach helping a \
fresher tailor their resume for one specific job posting. Be honest and specific -- do \
NOT invent skills or experience the resume doesn't support.

JOB POSTING
Title: {title}
Company: {company}
Description: {description}

RESUME TEXT
{resume}

Tasks:
1. matching_strengths: 2-4 things in the resume that genuinely already match this JD --
   phrase them as what to make sure stays prominent.
2. keyword_gaps: important keywords/skills from the JD that are missing or buried in the
   resume. For each, note briefly whether it looks like a genuine skill gap to learn, or
   just a wording/keyword mismatch (skill exists in the resume but phrased differently).
3. phrasing_suggestions: 3-5 concrete rewrite suggestions (e.g. "change 'helped with
   security monitoring' to 'monitored SIEM alerts for anomalous authentication events'")
   using only things the resume already supports -- never suggest claiming unproven skills.

Respond with JSON only, matching the schema.
"""


def _call_gemini(prompt: str, api_key: str) -> dict:
    url = API_URL.format(model=MODEL, key=api_key)
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "temperature": 0.3,
        },
    }
    status, raw = http_utils.request(
        url, method="POST", data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, timeout=60, max_attempts=4, backoff_seconds=4.0,
    )
    if status != 200:
        raise GeminiError(f"Gemini API returned HTTP {status}: {raw[:300]!r}")
    payload = json.loads(raw)
    text = payload["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def analyze(job: JobListing, api_key: str) -> dict | None:
    if not RESUME_PATH.exists():
        return None

    resume_text = RESUME_PATH.read_text(encoding="utf-8", errors="ignore")[:MAX_RESUME_CHARS]
    if not resume_text.strip():
        return None

    prompt = PROMPT_TEMPLATE.format(
        title=job.title, company=job.company,
        description=job.description_snippet or "(no description available)",
        resume=resume_text,
    )
    try:
        return _call_gemini(prompt, api_key)
    except Exception as exc:
        logger.error("Resume coaching failed: %s", exc)
        return None


def build_section_html(job: JobListing | None, result: dict | None) -> str:
    if not RESUME_PATH.exists():
        return f"""
        <h3 style="margin-bottom:4px;">Resume Tailoring</h3>
        <p style="color:#666;">Not enabled yet -- drop your resume as plain text into
        <code>data/resume.txt</code> and this section will start comparing it against
        each day's top-matched job.</p>
        """

    if job is None:
        return """
        <h3 style="margin-bottom:4px;">Resume Tailoring</h3>
        <p style="color:#666;">No job matched today to tailor against.</p>
        """

    if result is None:
        return """
        <h3 style="margin-bottom:4px;">Resume Tailoring</h3>
        <p style="color:#666;">Unavailable today (analysis failed) -- try again tomorrow.</p>
        """

    def bullets(items):
        return "".join(f"<li>{item}</li>" for item in items) or "<li>(none)</li>"

    return f"""
    <h3 style="margin-bottom:4px;">Resume Tailoring (vs. {job.title} @ {job.company})</h3>
    <p><strong>Already matches:</strong></p>
    <ul>{bullets(result.get('matching_strengths', []))}</ul>
    <p><strong>Keyword/skill gaps:</strong></p>
    <ul>{bullets(result.get('keyword_gaps', []))}</ul>
    <p><strong>Phrasing suggestions:</strong></p>
    <ul>{bullets(result.get('phrasing_suggestions', []))}</ul>
    """
