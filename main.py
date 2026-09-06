"""Single-shot entry point: runs the SOC Analyst job digest pipeline once.

Intended to be invoked once daily (by scheduler.py, Windows Task Scheduler,
or manually). Exits non-zero on failure so a task scheduler can flag it.
"""

from __future__ import annotations

import sys

from soc_job_agent.config import ConfigError, load_config
from soc_job_agent.logging_setup import setup_logging
from soc_job_agent.pipeline import run


def main() -> int:
    logger = setup_logging()
    try:
        config = load_config()
    except ConfigError as exc:
        logger.error("Configuration error: %s", exc)
        return 2

    try:
        run(config)
    except Exception:
        logger.exception("Pipeline run failed")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
