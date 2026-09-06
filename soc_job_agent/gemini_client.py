"""Gemini API client -- used only for judgment on an already-filtered
shortlist (relevance scoring, semantic dedup, ranking, summarization).

Deliberately does NOT use Google Search grounding: that tool requires a
billed Google Cloud project and returns 429 RESOURCE_EXHAUSTED on a
free/unbilled API key (verified against this project's key). Web sourcing
is handled entirely by linkedin_search.py instead, which keeps this module
cheap -- one small JSON-in/JSON-out call per daily run.
"""

from __future__ import annotations

import json
import logging

from . import http_utils
from .linkedin_search import JobListing

logger = logging.getLogger("soc_job_agent.gemini")

MODEL = "gemini-flash-lite-latest"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "ranked_jobs": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "job_id": {"type": "STRING"},
                    "reason": {"type": "STRING"},
                },
                "required": ["job_id", "reason"],
            },
        },
        "overall_summary": {"type": "STRING"},
    },
    "required": ["ranked_jobs", "overall_summary"],
}

PROMPT_TEMPLATE = """You are screening job listings for a fresher (0-1 year experience) \
who wants a SOC Analyst / Security Operations Center role in Pune or Mumbai, India.

Below is a JSON array of candidate listings that already passed basic keyword and \
location filters, but may still contain false positives (wrong seniority, not \
genuinely SOC-related, duplicates of the same underlying role at the same company).

Tasks:
1. Drop any listing that is NOT a genuine fresher/entry-level SOC-equivalent role \
(e.g. drop anything senior, or unrelated to security operations despite matching \
keywords).
2. If two listings are clearly the same underlying job (same company + near-identical \
title/description), keep only one.
3. Rank the remaining listings, best first, considering in priority order: \
(a) freshness/posting recency, (b) fresher/entry-level suitability, (c) SOC relevance, \
(d) location relevance (Pune/Mumbai preferred over Navi Mumbai/Thane).
4. Return AT MOST 10 listings.
5. For each, write one short sentence (<25 words) explaining why it fits a fresher \
SOC profile.
6. Write a 1-2 sentence overall_summary of today's shortlist for the top of an email.

Candidates (JSON):
{candidates_json}

Respond with JSON only, matching the required schema. Use the exact "job_id" values \
given -- do not invent or alter them.
"""


class GeminiError(RuntimeError):
    pass


def _call(prompt: str, api_key: str) -> dict:
    url = API_URL.format(model=MODEL, key=api_key)
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "temperature": 0.2,
        },
    }
    status, raw = http_utils.request(
        url,
        method="POST",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        timeout=60,
        max_attempts=5,
        backoff_seconds=4.0,
    )
    if status != 200:
        raise GeminiError(f"Gemini API returned HTTP {status}: {raw[:500]!r}")

    payload = json.loads(raw)
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise GeminiError(f"Unexpected Gemini response shape: {payload}") from exc

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise GeminiError(f"Gemini did not return valid JSON: {text[:500]!r}") from exc


def score_and_rank(jobs: list[JobListing], api_key: str) -> tuple[list[JobListing], dict[str, str], str]:
    """Returns (ranked jobs in order, {job_id: reason}, overall_summary).

    On any Gemini failure, falls back to the rule-filtered order (already
    sorted by recency) with a generic reason, so a Gemini outage never blocks
    the daily email entirely.
    """
    if not jobs:
        return [], {}, "No matching SOC Analyst fresher openings were found today."

    candidates = [
        {
            "job_id": job.job_id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "posted_date": job.posted_date.isoformat() if job.posted_date else "unknown",
            "seniority": job.seniority or "unknown",
            "description_snippet": job.description_snippet[:400],
        }
        for job in jobs
    ]
    prompt = PROMPT_TEMPLATE.format(candidates_json=json.dumps(candidates, indent=2))

    try:
        result = _call(prompt, api_key)
    except GeminiError as exc:
        logger.error("Gemini scoring failed, falling back to rule-based order: %s", exc)
        fallback_reasons = {j.job_id: "Matched SOC fresher keyword/location/date filters." for j in jobs[:10]}
        return jobs[:10], fallback_reasons, "Gemini scoring was unavailable; showing filtered results by recency."

    by_id = {job.job_id: job for job in jobs}
    ranked: list[JobListing] = []
    reasons: dict[str, str] = {}
    for entry in result.get("ranked_jobs", []):
        job = by_id.get(entry.get("job_id"))
        if job is None:
            logger.warning("Gemini returned unknown job_id %r, skipping", entry.get("job_id"))
            continue
        ranked.append(job)
        reasons[job.job_id] = entry.get("reason", "")

    summary = result.get("overall_summary", "")
    logger.info("Gemini ranked %d/%d candidates", len(ranked), len(jobs))
    return ranked[:10], reasons, summary
