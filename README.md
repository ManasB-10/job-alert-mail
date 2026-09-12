# SOC Analyst Career Digest Agent

Searches for recent SOC Analyst / entry-level security-operations job openings in
Pune, Mumbai, Navi Mumbai and Thane, and emails a ranked top-10 shortlist every
day at **08:00 IST (Asia/Kolkata)** -- plus a bundle of career-coaching sections
(skill-gap analysis, a mock SOC ticket, interview drill, resume tailoring,
LinkedIn keyword gaps, and application follow-up reminders) in the same email.

## How it works

1. **Search** (`soc_job_agent/linkedin_search.py`) — queries LinkedIn's public,
   no-login "guest" job search pages (no API key, no billing) across a small
   keyword x location grid, with a 30-day time-posted filter at the source.
2. **Cheap rule-based filtering** (`soc_job_agent/filters.py`) — location,
   title keywords (includes SOC/security-analyst titles, excludes
   senior/lead/L2+/manager-type titles), and posting age, all in plain Python,
   zero API cost.
3. **Detail enrichment** — only the survivors (capped at 30/day) get their job
   detail page fetched, to read LinkedIn's own seniority label and a
   description snippet.
4. **More rule-based filtering** — drops anything LinkedIn itself labels
   Mid-Senior/Director/Executive, or whose description states >1 year of
   required experience.
5. **History dedup** (`soc_job_agent/history.py`) — `data/seen_jobs.json`
   tracks what's already been emailed, so the same posting isn't repeated for
   30 days unless its title/company changes.
6. **Gemini scoring** (`soc_job_agent/gemini_client.py`) — only the remaining
   shortlist (typically <15 jobs) is sent to Gemini, which drops any
   remaining false positives, dedups near-identical postings, ranks by
   freshness/fresher-suitability/SOC-relevance/location, writes a one-line
   "why it fits" per job, and a short summary. **Not** used for web search.
7. **Archive** (`soc_job_agent/report_store.py`) — uploads the day's HTML
   report and a structured JSON record to an IDrive e2 (S3-compatible)
   bucket, before sending email, so a copy survives even if SMTP fails.
   Optional: skipped with a log line if IDrive e2 vars aren't set.
8. **Email** (`soc_job_agent/emailer.py`) — sends an HTML table via Brevo SMTP.

## Career-coaching sections

Each of these is independently fault-tolerant (`pipeline._safe`) -- if one
fails (e.g. Gemini overloaded), the others and the core job email still go
out. All are bundled into the one daily email, below the job listings.

| Section | Module | Cost | Needs |
|---|---|---|---|
| Skill Gap Insights | `skill_gap.py` | Free (keyword counting, no API) | Nothing -- builds up from postings seen over time (`data/job_corpus.jsonl`) |
| Mock SOC Ticket | `mock_shift.py` | 1 Gemini call/day | Nothing -- generates a new scenario + model answer daily, rotating through 10 alert types |
| Interview Drill | `interview_drill.py` | Free (curated bank, no API) | Nothing -- spaced-repetition over `interview_bank.py`'s ~20 Q&A |
| Resume Tailoring | `resume_coach.py` | 1 Gemini call/day (only if enabled) | **`data/resume.txt`** -- your resume as plain text |
| LinkedIn Keyword Gaps | `linkedin_coach.py` | Free (set difference, no API) | **`data/my_skills.txt`** -- your current LinkedIn skills, one per line |
| Application Tracker | `application_tracker.py` | Free | Nothing to view; use `track.py` to mark applications |

To activate resume tailoring and LinkedIn gap-checking, just create those two
files with your real content -- the section switches from "not enabled yet"
instructions to real output on the next run, no code changes needed.

### Tracking applications

No inbound email channel exists (would need a public webhook endpoint, out
of scope for a local script), so you track applications yourself with a CLI:

```powershell
python track.py apply 4462432240              # job_id from the email's Apply link, or paste the whole URL
python track.py status 4462432240 interview   # applied | interview | rejected | offer
python track.py list
```

The email's Application Tracker section then reminds you to follow up on
applications with no status update after 7/14/21 days, and nudges you about
recent matches you haven't marked as applied yet.

### Why not Gemini's built-in Google Search grounding?

It was tried first and consistently returned `429 RESOURCE_EXHAUSTED` on the
configured API key (grounding requires a billed Google Cloud project; this
key's project has no billing linked). Non-grounded Gemini calls work fine and
are used for scoring. If you later enable billing and want Gemini to do the
searching itself instead of LinkedIn scraping, that's a config change, not a
rewrite — ask and it can be swapped in.

## Setup

```powershell
# from the project directory
pip install -r requirements.txt   # installs tzdata (Windows has no built-in IANA tz db)
copy .env.example .env            # then fill in real values (already done in this repo's .env)
```

Required `.env` values (see `.env.example`):

```
GEMINI_API_KEY=
BREVO_SMTP_HOST=smtp-relay.brevo.com
BREVO_SMTP_PORT=587
BREVO_SMTP_USER=
BREVO_SMTP_PASSWORD=
EMAIL_FROM=
EMAIL_TO=
```

`EMAIL_FROM` must be a verified sender (or verified domain) in your Brevo
account, or Brevo will reject the send.

Optional -- daily report archiving to IDrive e2 (S3-compatible storage). Leave
blank to skip archiving entirely; the email still sends either way:

```
IDRIVE_E2_ENDPOINT=s3.us-west-2.idrivee2.com
IDRIVE_E2_REGION=us-west-2
IDRIVE_E2_ACCESS_KEY=
IDRIVE_E2_SECRET_KEY=
IDRIVE_E2_BUCKET=
```

`IDRIVE_E2_BUCKET` is the bucket **name** (e.g. `ai-agent`), not a hostname --
don't paste the full `bucket.s3.region.idrivee2.com` endpoint into it, that
breaks the path-style request the client builds
(`https://{endpoint}/{bucket}/{key}`).

Each run writes `reports/<YYYY-MM-DD>/report.html` (the exact email body) and
`reports/<YYYY-MM-DD>/report.json` (structured job list + stats) to the
bucket.

## Running

**One-off run** (useful for testing):

```powershell
python main.py
```

Exits with code `0` on success, `1` on a pipeline failure, `2` on missing/bad
`.env` config. Logs go to `logs/agent.log` (rotating) and the console.

**Continuous daily scheduler** (what actually gives you the 8 AM email every
day without you doing anything):

```powershell
python scheduler.py
```

This process runs forever, computing "next 08:00 Asia/Kolkata" explicitly via
Python's `zoneinfo` (not the OS clock/timezone setting), sleeping until then,
running the pipeline, and repeating. If the machine was off or the process
wasn't running at 08:00, it catches up and runs as soon as it's next started
that same day (tracked in `data/last_run_date.txt`), so you don't lose a day.

### Making it start automatically (no manual `python scheduler.py` each time)

**Currently active: a Startup-folder launcher (no admin rights needed).**
`SOC_Job_Agent_Scheduler.vbs` (in this repo, and copied into
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`) silently
launches `pythonw.exe scheduler.py` every time you log into Windows (Windows
runs everything in this per-user folder automatically at logon, no
elevation required). This is what's actually installed and running right
now. If you move the project or Python install, edit the two paths in the
`.vbs` file (both the copy in the Startup folder and this one). To remove
it: delete the `.vbs` file from the Startup folder (open it via Win+R ->
`shell:startup`).

**Alternative: Windows Scheduled Task** (adds auto-restart if the process
ever crashes, at the cost of needing one admin step). Run
`register_scheduled_task.ps1` **in an elevated PowerShell window** (Run as
Administrator) once:

```powershell
powershell -ExecutionPolicy Bypass -File "register_scheduled_task.ps1"
```

This registers a Windows Scheduled Task (`SOC_Job_Agent_Scheduler`) that
starts `scheduler.py` hidden (via `pythonw.exe`) at logon and restarts it if
it crashes. Task Scheduler registration itself requires an elevated/admin
prompt that a non-interactive process can't answer, which is why the
Startup-folder approach above is the one actually in use -- it needed no
admin step at all. If you do register the Scheduled Task later, remove the
Startup `.vbs` first so you don't end up with two schedulers running at
once.

To check the Startup one's running: Task Manager -> Details tab -> look for
`pythonw.exe`, or `Get-Process pythonw` in PowerShell.

To check the alternative Scheduled Task (if used) is running: Task Scheduler
app -> Task Scheduler Library -> `SOC_Job_Agent_Scheduler`. To stop/remove it:

```powershell
Unregister-ScheduledTask -TaskName "SOC_Job_Agent_Scheduler" -Confirm:$false
```

## Testing what you built

- `python main.py` — full pipeline once, sends a real email if any jobs
  survive filtering. Already verified working during development (search,
  filtering, Gemini scoring, and Brevo delivery all confirmed live).
- To re-test without waiting for new postings, temporarily delete or rename
  `data/seen_jobs.json` (otherwise already-emailed jobs are skipped for 30
  days by design).
- Check `logs/agent.log` for a full trace of each stage's candidate counts.

## Tuning

- Keywords/locations searched: `soc_job_agent/linkedin_search.py`
  (`KEYWORDS`, `LOCATIONS`).
- Title include/exclude rules, freshness window: `soc_job_agent/filters.py`.
- Dedup cooldown (currently 30 days): `history.RESEND_COOLDOWN_DAYS`.
- Max jobs enriched per run (cost/time cap): `pipeline.MAX_DETAIL_FETCHES`.
- Gemini model: `gemini_client.MODEL` (currently `gemini-flash-lite-latest`;
  `gemini-flash-latest` was flaky/overloaded on this key at time of writing).
- Skill keyword list: `skills_data.SKILL_KEYWORDS` -- add tools/certs here to
  track more of them in Skill Gap Insights and LinkedIn Keyword Gaps.
- Interview questions per day: `interview_drill.QUESTIONS_PER_DAY`; the bank
  itself is `interview_bank.QUESTIONS` -- just add more dicts to grow it.
- Mock ticket scenario types: `mock_shift.SCENARIO_TYPES`.
- Follow-up reminder cadence: `application_tracker.FOLLOWUP_CHECKPOINTS_DAYS`.

## Notes / limitations

- LinkedIn's guest search endpoint is unofficial (no API key exists for it);
  its HTML structure could change and break parsing. All parsing is
  defensive (missing fields degrade gracefully, not fatally), but if LinkedIn
  changes their markup, `linkedin_search.py`'s regexes will need updating.
- "Experience requirement" in the email reflects LinkedIn's own seniority
  label when available; LinkedIn doesn't expose it on search-result cards,
  only detail pages, which is why detail-page fetching exists at all.
- If Gemini is down/rate-limited, the email still sends (falls back to the
  rule-filtered, recency-sorted list with a generic reason) rather than
  silently failing.
