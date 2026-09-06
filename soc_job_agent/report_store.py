"""Archives each day's report to IDrive e2 (S3-compatible object storage).

Optional: if IDrive e2 credentials aren't configured, archiving is skipped
entirely and logged once -- it never blocks the email pipeline. Likewise, an
upload failure (bad credentials, network issue) is logged and swallowed
rather than raised, since losing the archive copy is not worth failing the
whole day's run when the email itself may already have been sent.
"""

from __future__ import annotations

import json
import logging
from datetime import date

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from .config import Config
from .linkedin_search import JobListing

logger = logging.getLogger("soc_job_agent.report_store")


def _client(config: Config):
    return boto3.client(
        "s3",
        endpoint_url=f"https://{config.idrive_endpoint}",
        region_name=config.idrive_region,
        aws_access_key_id=config.idrive_access_key,
        aws_secret_access_key=config.idrive_secret_key,
        config=BotoConfig(s3={"addressing_style": "path"}, retries={"max_attempts": 3, "mode": "standard"}),
    )


def upload_daily_report(
    config: Config,
    today: date,
    html_body: str,
    jobs: list[JobListing],
    reasons: dict[str, str],
    summary: str,
    stats: dict,
) -> list[str] | None:
    """Uploads the day's HTML email body + a structured JSON record.

    Returns the list of object keys written, or None if archiving was
    skipped (not configured) or failed.
    """
    if not config.idrive_configured:
        logger.debug("IDrive e2 not configured -- skipping report archive.")
        return None

    date_str = today.isoformat()
    html_key = f"reports/{date_str}/report.html"
    json_key = f"reports/{date_str}/report.json"

    record = {
        "date": date_str,
        "summary": summary,
        "stats": stats,
        "jobs": [
            {
                "job_id": job.job_id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "posted_date": job.posted_date.isoformat() if job.posted_date else None,
                "seniority": job.seniority,
                "source": job.source,
                "reason": reasons.get(job.job_id, ""),
            }
            for job in jobs
        ],
    }

    try:
        client = _client(config)
        client.put_object(
            Bucket=config.idrive_bucket,
            Key=html_key,
            Body=html_body.encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )
        client.put_object(
            Bucket=config.idrive_bucket,
            Key=json_key,
            Body=json.dumps(record, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
    except (BotoCoreError, ClientError) as exc:
        logger.error("Failed to archive daily report to IDrive e2: %s", exc)
        return None

    logger.info("Archived daily report to IDrive e2: %s, %s", html_key, json_key)
    return [html_key, json_key]
