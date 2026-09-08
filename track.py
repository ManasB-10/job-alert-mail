"""CLI to track job applications, since there's no inbound email channel.

Usage:
  python track.py apply <job_id_or_url> [notes...]
  python track.py status <job_id_or_url> <applied|interview|rejected|offer> [notes...]
  python track.py list

job_id is the numeric id at the end of a job's LinkedIn URL (also shown by
`list`); you can also just paste the full URL from the email and it'll be
extracted automatically.
"""

from __future__ import annotations

import re
import sys

from soc_job_agent import application_tracker, history

JOB_ID_RE = re.compile(r"(\d{6,})")


def _extract_job_id(raw: str) -> str:
    match = JOB_ID_RE.search(raw)
    return match.group(1) if match else raw


def cmd_apply(args: list[str]) -> int:
    if not args:
        print("Usage: python track.py apply <job_id_or_url> [notes...]")
        return 1
    job_id = _extract_job_id(args[0])
    notes = " ".join(args[1:])

    job_hist = history.load_all()
    known = job_hist.get(job_id, {})
    application_tracker.mark_applied(
        job_id, title=known.get("title", ""), company=known.get("company", ""), notes=notes
    )
    print(f"Marked {job_id} ({known.get('title', 'unknown title')} @ {known.get('company', 'unknown')}) as applied.")
    return 0


def cmd_status(args: list[str]) -> int:
    if len(args) < 2:
        print("Usage: python track.py status <job_id_or_url> <applied|interview|rejected|offer> [notes...]")
        return 1
    job_id = _extract_job_id(args[0])
    status = args[1]
    notes = " ".join(args[2:])
    if not application_tracker.update_status(job_id, status, notes):
        print(f"No tracked application found for {job_id} -- run 'apply' first.")
        return 1
    print(f"Updated {job_id} to status={status!r}.")
    return 0


def cmd_list(args: list[str]) -> int:
    applications = application_tracker.load_applications()
    if not applications:
        print("No tracked applications yet.")
        return 0
    for job_id, app in applications.items():
        print(f"{job_id}: {app.get('title', '?')} @ {app.get('company', '?')} "
              f"-- {app.get('status', '?')} (applied {app.get('applied_date', '?')})"
              + (f" -- {app['notes']}" if app.get("notes") else ""))
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    command, *args = sys.argv[1:]
    commands = {"apply": cmd_apply, "status": cmd_status, "list": cmd_list}
    handler = commands.get(command)
    if handler is None:
        print(f"Unknown command {command!r}. Use apply, status, or list.")
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
