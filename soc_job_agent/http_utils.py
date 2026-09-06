"""Small retrying HTTP helper built on urllib (no extra dependency)."""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request

logger = logging.getLogger("soc_job_agent.http")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def request(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict | None = None,
    timeout: int = 20,
    max_attempts: int = 3,
    backoff_seconds: float = 2.0,
) -> tuple[int, bytes]:
    """GET/POST with retries + exponential backoff. Returns (status, body).

    Non-retryable HTTP errors are returned as (status, body) rather than
    raised, so callers can decide (e.g. a 404 for one job listing shouldn't
    abort the whole run). Network-level failures raise after exhausting
    retries.
    """
    merged_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        merged_headers.update(headers)

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(url, data=data, headers=merged_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            body = exc.read()
            if exc.code in RETRYABLE_STATUS and attempt < max_attempts:
                wait = backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "HTTP %s from %s (attempt %d/%d), retrying in %.1fs",
                    exc.code, url, attempt, max_attempts, wait,
                )
                time.sleep(wait)
                last_exc = exc
                continue
            return exc.code, body
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < max_attempts:
                wait = backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Network error calling %s (attempt %d/%d): %s. Retrying in %.1fs",
                    url, attempt, max_attempts, exc, wait,
                )
                time.sleep(wait)
                continue

    assert last_exc is not None
    raise last_exc
