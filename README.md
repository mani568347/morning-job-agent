# Morning Job Agent

While you sleep, an agent searches job boards, scores each posting against
your resume, and leaves ten matched jobs with draft cover letters in
`reports/` when you wake up.

**Stack:** Python · Pydantic AI · JSearch (RapidAPI) · Gemini Flash · GitHub Actions cron (05:30 IST)

## Where the job data comes from (and why not scraping)

Jobs come from **JSearch on RapidAPI** — a licensed aggregator of Google for
Jobs, 200 free requests/month, best India coverage. We do **not** scrape
LinkedIn or Indeed: there is no self-serve API, the ToS prohibit it, and
hiQ's famous CFAA win ended in a $500k judgment and a permanent injunction
against scraping LinkedIn. A licensed API is both legal and less work.

Budget: 4 saved queries × 30 nights ≈ 120 requests/month. The pipeline
refuses to fetch once `monthly_request_budget` in `config/queries.yaml` is
reached for the month.

## Setup (once)

1. **Keys**
   - JSearch: join at `rapidapi.com/rapidapi/api/jsearch-p` → copy your
     RapidAPI key.
   - Gemini: free key at `aistudio.google.com/apikey`.
   - Locally: copy `.env.example` to `.env`. On GitHub: add both as repo
     Secrets (`Settings → Secrets and variables → Actions`).

2. **Parse your resume once** (the nightly job never re-parses it):
   ```bash
   pip install -r requirements.txt
   python -m morning_job_agent.parse_resume path/to/resume.pdf
   ```
   Review `data/resume.json`, fix anything wrong, commit it.

3. **Edit queries** in `config/queries.yaml` (3–5 saved searches).

4. **Run it today, manually:**
   ```bash
   python -m morning_job_agent
   ```
   Output lands in `reports/YYYY-MM-DD.md` (IST date).

5. **Schedule it:** push the repo to GitHub (public = free unlimited runner
   minutes). The `daily.yml` workflow runs at `cron: '0 0 * * *'` UTC, i.e.
   05:30 IST, and commits the report plus dedupe state back to the repo.

## Gotchas, handled

- **60-day scheduler disable:** GitHub auto-disables cron on public repos
  with no activity for 60 days, and bot commits don't count as activity.
  `keepalive.yml` pushes an empty commit when the repo goes quiet — but it
  needs a `KEEPALIVE_PAT` secret (fine-grained PAT, contents:write) to
  count as real push activity. Add it, or just commit something monthly.
- **Dedupe:** `data/seen.json` stores `sha1(company|title|location)`;
  entries older than 60 days are pruned so a re-post can resurface.
- **Scoring is forced structured output:** every job gets an int 0–100 plus
  a one-line reason, then the top 10 get cover letters. Cover letters only
  use facts from the resume — no invented experience.
- **Cost guards:** max 60 jobs scored per run; request budget checked
  before any API call.

## Layout

```
config/queries.yaml      saved searches + budget
data/resume.json         parsed resume (commit it)
data/seen.json           dedupe state (workflow commits updates)
data/usage.json          monthly request counter
reports/                 one markdown report per morning
src/morning_job_agent/
  pipeline.py            fetch → dedupe → score → report
  jsearch.py             RapidAPI client
  dedupe.py              hash + seen-store
  scoring.py             Pydantic AI agents (Gemini Flash)
  report.py              markdown renderer
  parse_resume.py        one-time local tool
```

## Making it yours

Swap locations/queries in `config/queries.yaml`; retune the scoring agent's
personality in `scoring.py` instructions; raise `num_jobs` per query if you
want deeper recall (it's still one request). To add SerpApi as a second
source, implement a sibling of `jsearch.py` returning `list[Job]` and append
to `all_jobs` in `pipeline.py` — dedupe handles the overlap.
