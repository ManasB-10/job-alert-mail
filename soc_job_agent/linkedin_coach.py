"""LinkedIn skills-section keyword gap check.

Deterministic set difference (no Gemini call) between your self-maintained
skills list and the skill_gap keyword ranking already computed from the job
corpus. Reads data/my_skills.txt (one skill/keyword per line, matched loosely
against skills_data's display names) -- explains how to enable itself if
that file doesn't exist yet.
"""

from __future__ import annotations

from pathlib import Path

from . import skills_data
from .skill_gap import MIN_CORPUS_SIZE, analyze

MY_SKILLS_PATH = Path(__file__).resolve().parent.parent / "data" / "my_skills.txt"
TOP_N_TO_CHECK = 15


def _load_my_skills() -> set[str]:
    if not MY_SKILLS_PATH.exists():
        return set()
    lines = MY_SKILLS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    return {line.strip().lower() for line in lines if line.strip()}


def find_gaps(corpus_records: list[dict]) -> dict | None:
    my_skills = _load_my_skills()
    if not my_skills:
        return None

    result = analyze(corpus_records)
    if result["total_postings"] < MIN_CORPUS_SIZE:
        return {"total_postings": result["total_postings"], "missing": [], "too_little_data": True}

    top_demanded = result["ranked"][:TOP_N_TO_CHECK]
    missing = [
        (skill, count, pct)
        for skill, count, pct in top_demanded
        if skill.lower() not in my_skills
    ]
    return {"total_postings": result["total_postings"], "missing": missing, "too_little_data": False}


def build_section_html(gap_result: dict | None) -> str:
    if not MY_SKILLS_PATH.exists():
        return """
        <h3 style="margin-bottom:4px;">LinkedIn Keyword Gaps</h3>
        <p style="color:#666;">Not enabled yet -- list your current LinkedIn skills
        section, one per line, in <code>data/my_skills.txt</code>, and this section
        will flag high-demand keywords missing from it.</p>
        """

    if gap_result is None or gap_result.get("too_little_data"):
        return """
        <h3 style="margin-bottom:4px;">LinkedIn Keyword Gaps</h3>
        <p style="color:#666;">Still building up enough job data for a reliable
        comparison -- check back in a few days.</p>
        """

    missing = gap_result["missing"]
    if not missing:
        return """
        <h3 style="margin-bottom:4px;">LinkedIn Keyword Gaps</h3>
        <p style="color:#2a7;">Your listed skills already cover the top in-demand
        keywords from recent postings. Nice.</p>
        """

    items = "".join(
        f"<li>{skill} -- appears in {pct}% of recent postings ({count} seen)</li>"
        for skill, count, pct in missing
    )
    return f"""
    <h3 style="margin-bottom:4px;">LinkedIn Keyword Gaps</h3>
    <p style="color:#666;margin-top:0;">High-demand keywords from recent postings that
    aren't in your <code>data/my_skills.txt</code> list -- add any you genuinely have to
    your LinkedIn skills section (don't add ones you don't actually have):</p>
    <ul>{items}</ul>
    """
