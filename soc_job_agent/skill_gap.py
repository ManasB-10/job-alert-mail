"""Skill-gap analysis: what to learn next, based on real local job postings.

Purely deterministic keyword-frequency counting over the rolling job corpus
(corpus.py) -- no Gemini call, so it's free and reproducible. This answers
"what do Pune/Mumbai SOC fresher postings actually ask for" rather than
generic internet advice.
"""

from __future__ import annotations

from collections import Counter

from . import skills_data

MIN_CORPUS_SIZE = 5  # below this, frequencies are too noisy to be useful


def analyze(corpus_records: list[dict]) -> dict:
    """Returns {"total_postings": int, "ranked": [(skill, count, pct), ...]}."""
    total = len(corpus_records)
    counter: Counter[str] = Counter()

    for record in corpus_records:
        text = f"{record.get('title', '')} {record.get('description_snippet', '')}"
        matched = skills_data.extract_matches(text)
        counter.update(matched)

    ranked = [
        (skill, count, round(100 * count / total, 1) if total else 0.0)
        for skill, count in counter.most_common()
    ]
    return {"total_postings": total, "ranked": ranked}


def build_section_html(corpus_records: list[dict]) -> str:
    result = analyze(corpus_records)
    total = result["total_postings"]

    if total < MIN_CORPUS_SIZE:
        return f"""
        <h3 style="margin-bottom:4px;">Skill Gap Insights</h3>
        <p style="color:#666;">Still building up data ({total} postings seen so far) --
        check back in a few days for a reliable skill-demand ranking.</p>
        """

    rows = []
    for skill, count, pct in result["ranked"][:12]:
        category = skills_data.category_of(skill)
        rows.append(f"""
        <tr>
          <td style="padding:6px;border:1px solid #ddd;">{skill}</td>
          <td style="padding:6px;border:1px solid #ddd;color:#666;">{category}</td>
          <td style="padding:6px;border:1px solid #ddd;">{pct}% of postings ({count}/{total})</td>
        </tr>
        """)

    if not rows:
        return f"""
        <h3 style="margin-bottom:4px;">Skill Gap Insights</h3>
        <p style="color:#666;">No recognized tools/skills/certs matched in the last
        {total} postings' descriptions. The keyword list in skills_data.py may need
        expanding.</p>
        """

    return f"""
    <h3 style="margin-bottom:4px;">Skill Gap Insights</h3>
    <p style="color:#666;margin-top:0;">Based on {total} SOC fresher postings seen in
    Pune/Mumbai over the last ~90 days -- ranked by how often each appears:</p>
    <table style="border-collapse:collapse;width:100%;font-size:13px;">
      <thead>
        <tr style="background:#f2f2f2;">
          <th style="padding:6px;border:1px solid #ddd;text-align:left;">Skill/Tool/Cert</th>
          <th style="padding:6px;border:1px solid #ddd;text-align:left;">Category</th>
          <th style="padding:6px;border:1px solid #ddd;text-align:left;">Demand</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
    """
