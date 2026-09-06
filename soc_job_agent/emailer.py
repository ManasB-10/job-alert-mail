"""Brevo SMTP email delivery."""

from __future__ import annotations

import logging
import smtplib
import time
from datetime import date
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import Config
from .filters import is_recent
from .linkedin_search import JobListing

logger = logging.getLogger("soc_job_agent.emailer")

MAX_SEND_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 5.0


def _experience_text(job: JobListing) -> str:
    if job.seniority:
        return job.seniority
    return "Not specified (filtered as fresher/entry-level match)"


def _posted_text(job: JobListing, today: date) -> str:
    if job.posted_date is None:
        return "Unknown"
    age = (today - job.posted_date).days
    age_text = "today" if age <= 0 else f"{age} day{'s' if age != 1 else ''} ago"
    note = "" if is_recent(job, today) else " (older listing, included to reach 10)"
    return f"{job.posted_date.isoformat()} ({age_text}){note}"


def build_email_html(
    jobs: list[JobListing],
    reasons: dict[str, str],
    overall_summary: str,
    today: date,
) -> str:
    if not jobs:
        return f"""
        <p>{overall_summary}</p>
        <p>No SOC Analyst fresher openings in Pune/Mumbai matched today's filters.
        The agent will try again tomorrow.</p>
        """

    rows = []
    for i, job in enumerate(jobs, start=1):
        reason = reasons.get(job.job_id, "")
        rows.append(f"""
        <tr>
          <td style="padding:8px;border:1px solid #ddd;vertical-align:top;">{i}</td>
          <td style="padding:8px;border:1px solid #ddd;vertical-align:top;">
            <strong>{job.title}</strong><br/>
            <span style="color:#555;">{job.company}</span>
          </td>
          <td style="padding:8px;border:1px solid #ddd;vertical-align:top;">{job.location}</td>
          <td style="padding:8px;border:1px solid #ddd;vertical-align:top;">{_experience_text(job)}</td>
          <td style="padding:8px;border:1px solid #ddd;vertical-align:top;">{_posted_text(job, today)}</td>
          <td style="padding:8px;border:1px solid #ddd;vertical-align:top;">{job.source}</td>
          <td style="padding:8px;border:1px solid #ddd;vertical-align:top;">
            <a href="{job.url}">Apply</a>
          </td>
          <td style="padding:8px;border:1px solid #ddd;vertical-align:top;">{reason}</td>
        </tr>
        """)

    return f"""
    <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#222;">
      <p>{overall_summary}</p>
      <table style="border-collapse:collapse;width:100%;">
        <thead>
          <tr style="background:#f2f2f2;">
            <th style="padding:8px;border:1px solid #ddd;text-align:left;">#</th>
            <th style="padding:8px;border:1px solid #ddd;text-align:left;">Title / Company</th>
            <th style="padding:8px;border:1px solid #ddd;text-align:left;">Location</th>
            <th style="padding:8px;border:1px solid #ddd;text-align:left;">Experience</th>
            <th style="padding:8px;border:1px solid #ddd;text-align:left;">Posted</th>
            <th style="padding:8px;border:1px solid #ddd;text-align:left;">Source</th>
            <th style="padding:8px;border:1px solid #ddd;text-align:left;">Link</th>
            <th style="padding:8px;border:1px solid #ddd;text-align:left;">Why it fits</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
      <p style="color:#888;font-size:12px;margin-top:16px;">
        Sent automatically by your SOC Analyst job-monitoring agent.
      </p>
    </div>
    """


def send_email(config: Config, subject: str, html_body: str) -> None:
    message = MIMEMultipart("alternative")
    message["Subject"] = Header(subject, "utf-8")
    message["From"] = config.email_from
    message["To"] = config.email_to
    message.attach(MIMEText(html_body, "html", "utf-8"))

    last_exc: Exception | None = None
    for attempt in range(1, MAX_SEND_ATTEMPTS + 1):
        try:
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as server:
                server.starttls()
                server.login(config.smtp_user, config.smtp_password)
                server.sendmail(config.email_from, [config.email_to], message.as_string())
            logger.info("Email sent to %s (subject=%r)", config.email_to, subject)
            return
        except (smtplib.SMTPException, OSError) as exc:
            last_exc = exc
            logger.warning("SMTP send attempt %d/%d failed: %s", attempt, MAX_SEND_ATTEMPTS, exc)
            if attempt < MAX_SEND_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    raise RuntimeError(f"Failed to send email after {MAX_SEND_ATTEMPTS} attempts") from last_exc
