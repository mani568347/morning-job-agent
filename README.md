# Morning Job Agent

An autonomous job-hunting agent that runs every morning while you sleep. It searches live job
listings, scores each posting against your resume with Gemini, keeps the ten best matches, drafts
cover letters for the top five, and commits a readable markdown report back to this repository —
no dashboard to open, no inbox to filter.

**Stack:** Python 3.12 · Pydantic AI · JSearch (RapidAPI) · Gemini Flash · GitHub Actions cron

---

## Key features

| Feature | What it actually does |
|---|---|
| Resume-profile matching | Your resume is parsed once into `data/resume.json`. Each scoring call sends that whole profile (name, summary, skills, target titles, locations, years of experience, education, projects) plus the job's title, company, location, remote flag, posting date and description. |
| Forced structured scoring | The scoring agent must return an `int` 0–100 plus a one-line reason (≤ 160 chars) — validated by a Pydantic `output_type`, so there is no prose to parse. |
| Strict scorer | Instructed to be hard to please (90+ only for near-perfect matches) and to weigh skills, seniority, location and role title. |
| Cross-run deduplication | `sha1(company \| title \| location)` fingerprints — each field lower-cased and reduced to alphanumeric words first, so boards repeating the same posting under a slightly different title still collapse to one hash. Stored in `data/seen.json`; entries older than 60 days are pruned so a re-post can resurface. |
| Honest cover letters | Drafts for the top 5 only, 150–220 words, constrained to facts present in the resume — instructed never to invent experience. |
| Cost discipline | One JSearch request per saved query, a hard monthly request budget that is checked *before* any call, a cap on how many jobs get scored per run, and a shared counter committed in `data/usage.json`. |
| Free-tier resilience | Gemini calls are paced (≥ 13 s apart), retried on 429/503 with backoff, and fall back to a second model with its own quota pool. |
| Zero-infrastructure automation | GitHub Actions runs it on a cron and pushes the report, the dedupe state and the budget counter back to `main`. |

---

## How it works

```
Resume (data/resume.json)
   │
   ▼
JSearch API ──► Job fetching ──► Deduplication ──► Gemini AI scoring ──► Top 10 jobs
 (5 saved queries)  (search-v2)   (sha1 seen-store)   (0–100 + reason)      │
                                                                            ▼
        main branch  ◄── GitHub Actions  ◄── Daily report  ◄── Cover letters (top 5)
```

1. **Load** — environment keys, `config/queries.yaml`, `data/resume.json`, `data/seen.json`.
2. **Budget guard** — if `requests used this month + number of queries` exceeds
   `monthly_request_budget`, the run stops before spending anything.
3. **Fetch** — one `GET /search-v2` request per saved query, asking for up to 30 jobs each from the
   last week (fewer may come back); a failing query is logged and skipped rather than killing the
   night.
4. **Dedupe + age filter** — drop anything already seen, and anything dated older than
   `max_age_days` (7); postings that arrive without a usable date are kept, not discarded.
5. **Score** — at most 25 jobs are scored per run to stay inside the free-tier quota; results are
   sorted by score and the top 10 are shortlisted.
6. **Draft** — cover letters for the top 5; ranks 6–10 are listed with their score and reason.
7. **Report** — `reports/YYYY-MM-DD.md` (IST date) with a summary table and one section per job.
8. **Persist** — dedupe state and the monthly request counter are rewritten, then the workflow
   commits and pushes all three files.

### Data source, and why not scraping

Jobs come from **JSearch on RapidAPI**, a commercial job-listings API — one HTTP request per saved
query. This project deliberately does **not** scrape LinkedIn or Indeed: there is no self-serve API,
the terms of service prohibit it, and hiQ's early CFAA win ended in a $500k judgment plus a
permanent injunction against scraping LinkedIn. A licensed API is both legal and less work.

The nightly spend is controlled by `monthly_request_budget` in `config/queries.yaml` (currently
**195**), which the pipeline enforces itself before issuing any request — treat it as our own
ceiling, sized to stay inside whatever quota the API account carries.

---

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.12 |
| Agent framework | Pydantic AI — `Agent` with Pydantic AI's own `GoogleModel` / `GoogleProvider` |
| Models | `MODEL_NAMES = ["gemini-3.6-flash", "gemini-flash-lite-latest"]` — primary, then a fallback with a separate quota pool; each free tier allows ~5 requests/minute per model |
| Job source | JSearch (RapidAPI) `search-v2`, via `httpx` |
| Data models | Pydantic v2 (`Resume`, `Job`, `ScoreResult`, `ScoredJob`, `SeenStore`) |
| Config / state | YAML (`config/queries.yaml`) + JSON files under `data/` |
| Resume parsing | `pdfplumber` (local, one-time tool) |
| Output | Markdown report in `reports/` |
| Scheduler | GitHub Actions `schedule` cron, `ubuntu-latest` |

---

## Project structure

```
.
├── .github/workflows/
│   ├── daily.yml              nightly run: install deps, run agent, commit report
│   └── keepalive.yml          weekly empty commit to reset GitHub's 60-day cron pause
├── config/
│   └── queries.yaml           saved searches, max_age_days, monthly_request_budget
├── data/
│   ├── resume.json            parsed resume — input to every score (contact details removed)
│   ├── seen.json              sha1 dedupe state, updated and committed by the workflow
│   ├── seen.run1.json         snapshot of the dedupe store from the first run
│   └── usage.json             JSearch requests used, keyed by YYYY-MM
├── reports/
│   ├── 2026-09-23.md          generated (early run; slightly older stats wording)
│   ├── 2026-09-27.md          generated by the verified GitHub Actions run
│   └── sample.md              hand-written mock, shows the layout only
├── src/morning_job_agent/
│   ├── __init__.py            package marker + Windows-safe stdout reconfigure
│   ├── __main__.py            `python -m morning_job_agent` entry point
│   ├── pipeline.py            orchestration: guard → fetch → dedupe → score → report
│   ├── jsearch.py             RapidAPI client (search-v2, retries, parsing)
│   ├── dedupe.py              normalisation + sha1 hash + new-job filter
│   ├── scoring.py             Gemini scoring and cover-letter agents, pacing and fallback
│   ├── report.py              markdown renderer, IST-dated filename
│   ├── models.py              shared Pydantic models
│   ├── config.py              paths, .env loading, seen/usage stores
│   └── parse_resume.py        one-time local tool (PDF/txt → data/resume.json)
├── .env.example               variable names only — no values
├── .gitignore                 keeps .env, .venv/, *.log and the resume PDF out of Git
├── requirements.txt           runtime dependencies
└── README.md
```

---

## Automation

`.github/workflows/daily.yml` is the scheduler:

```yaml
on:
  schedule:
    - cron: "0 0 * * *"   # 00:00 UTC = 05:30 IST
  workflow_dispatch: {}   # manual runs from the Actions tab
```

- Installs `requirements.txt`, then runs the agent as `PYTHONPATH: src python -m morning_job_agent`.
- Both keys reach the step as environment variables from repo Secrets; the scoring code also
  accepts `GOOGLE_API_KEY` as an alias for `GEMINI_API_KEY` when running locally.
- A `Commit report + state` step adds `reports/` and `data/`, and pushes with
  `permissions: contents: write` — so the report for each morning lives in the repository history.
- The scheduled trigger carries no branch filter, so it runs on the default branch (`main`).
- Duration is dominated by Gemini pacing, not by the API work: one measured full run took
  **30m54s** for 24 scores + 5 cover letters.
- **Caveat:** GitHub pauses scheduled workflows on public repos after 60 days with no *human*
  activity, and `GITHUB_TOKEN` commits do not count. `keepalive.yml` (weekly, Mondays 06:00 UTC)
  pushes an empty commit once the repo has been quiet for 45 days, but only resets the timer if a
  `KEEPALIVE_PAT` secret (fine-grained PAT, `contents: write`) is configured.

Verified run (manual `workflow_dispatch`, 2026-09-27): 28 jobs fetched → 24 new after dedupe →
24 scored with zero failures → 10 shortlisted → 5 cover letters drafted → report committed as
`d207473` and pushed to `main`.

---

## Setup and configuration

### 1. API keys

| Variable | Where it comes from |
|---|---|
| `RAPID_API_KEY` | Subscribe to the JSearch endpoint on RapidAPI (`rapidapi.com/rapidapi/api/jsearch-p`) and copy the `X-RapidAPI-Key` from your RapidAPI apps dashboard. |
| `GEMINI_API_KEY` | Create a key in Google AI Studio (`aistudio.google.com/apikey`). Locally, `GOOGLE_API_KEY` is accepted as an alias. |

Locally, copy the template and fill it in:

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

On GitHub, add both under **Settings → Secrets and variables → Actions** with exactly those names.
`.env` is gitignored and is never read by the workflow.

### 2. Dependencies

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Parse your resume once

The nightly run never re-parses your resume — this is a one-time local step.

```bash
PYTHONPATH=src python -m morning_job_agent.parse_resume path/to/resume.pdf
```

Review `data/resume.json` and correct anything the model got wrong. For a public repository, strip
contact details (phone, email) and keep only what job matching needs: skills, titles, locations,
experience, education, projects.

### 4. Choose your searches

`config/queries.yaml` — each entry costs exactly one API request per night:

```yaml
queries:
  - name: "Django developer (remote)"
    query: "django developer"
    location: "India"
    remote: true

max_age_days: 7             # ignore postings older than this
monthly_request_budget: 195 # hard stop, checked before any request
```

Five queries × 30 nights ≈ 150 of the 195 monthly budget; adding queries eats that margin quickly.

### 5. Run it locally

```bash
PYTHONPATH=src python -m morning_job_agent
```

The report lands in `reports/<IST date>.md`. Useful console markers: `[fetch]` per query,
`[score NN]` per scored job, `[warn]` for a recovered failure, `[stop]` when the budget is spent.

> `PYTHONPATH=src` is required everywhere — the package lives under `src/` and there is no install
> step. The workflow sets it for exactly this reason.

---

## Generated reports

One file per morning, named by IST date, e.g. `reports/2026-09-27.md`:

- **Summary table** — rank, score, job title linked to the posting, company, location, and the
  one-line reason for the score.
- **Stats block** — `Fetched | New after dedupe | Scored successfully | Shortlisted`, plus
  `JSearch requests this month: N / <monthly_request_budget>`.
- **Per-job section** — location, remote flag, direct apply URL, and a draft cover letter for the
  top five. Ranks 6–10 carry a note that no letter was drafted because quota was spent on scoring.

Reports accumulate in the repository, so the history doubles as an application log you can browse by
day — `reports/2026-09-27.md` is a complete generated example. (Earlier reports such as
`reports/2026-09-23.md` use a slightly different stats label, and `reports/sample.md` is a
hand-written mock from the initial scaffold, not model output.)

---

## Security

- **No secrets in the repository.** Keys are read from `.env` locally and from GitHub Actions
  Secrets in CI; neither is committed. `.env.example` ships with empty values.
- **`.env` is gitignored**, along with `__pycache__/`, `*.pyc`, `.venv/`, `*.log` and
  `reports/*.draft.md`. The personal resume PDF is ignored by its exact path
  (`data/mani (1).pdf`) — only the redacted, contact-free `data/resume.json` is committed. If you
  keep your CV under a different filename, add it to `.gitignore` yourself before committing.
- **Logs are safe to read.** GitHub masks injected secrets as `***` in workflow logs, and the agent
  never prints key material.
- **Least privilege.** `daily.yml` requests only `contents: write`; nothing else.
- If a key is ever pushed or pasted anywhere, revoke and regenerate it rather than rewriting
  history.

---

## Future improvements

Not implemented — candidates only:

- Multiple job sources (e.g. a SerpApi client returning `list[Job]`) to widen recall; the dedupe
  layer already handles overlap.
- Apply-link triage and an application status tracker (applied / interview / rejected) so the
  reports can roll up into a pipeline view.
- Feedback loop: feed your own ratings back into scoring prompts so the ranking learns your
  preferences.
- Richer resume signals (per-project skill mapping, role-target variants) and multiple profiles for
  different job families.
- A test suite around dedupe, config loading and report rendering, plus a smoke test that mocks
  both API clients.
- Packaging (`pyproject.toml`) so `python -m morning_job_agent` works without `PYTHONPATH`.
- Delivery of the day's summary to email or Telegram as an optional channel.
- Quota-aware scheduling: skip scoring entirely when the Gemini daily cap is already spent, and
  reserve it for the highest-value queries.

---

*Built as a self-contained agent project: licensed public APIs only, no scraping, and every job
score and cover letter generated by the model at run time.*
