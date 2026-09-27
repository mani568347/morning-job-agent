"""The nightly pipeline: fetch -> dedupe -> score -> report."""

import sys
from datetime import datetime, timezone, timedelta

from . import config
from .dedupe import filter_new, job_hash
from .jsearch import fetch_jobs
from .models import Job, SeenEntry
from .report import render, write_report
from .scoring import _api_key, score_and_select


def _within_age(job: Job, max_age_days: int) -> bool:
    if not job.posted_at:
        return True
    try:
        posted = datetime.fromisoformat(job.posted_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    age = datetime.now(timezone.utc) - posted
    return age <= timedelta(days=max_age_days)


def run() -> int:
    config.load_env()
    rapid_key = config.require_env("RAPID_API_KEY")
    _api_key()  # fail before spending JSearch requests if Gemini key is missing

    cfg = config.load_queries_config()
    resume = config.load_resume()
    seen = config.load_seen()
    budget = int(cfg.get("monthly_request_budget", 195))

    used = config.requests_used_this_month()
    needed = len(cfg["queries"])
    if used + needed > budget:
        print(f"[stop] {used} of {budget} monthly JSearch requests already used; "
              f"this run needs {needed}. Skipping fetch, no report written.")
        return 1

    all_jobs: list[Job] = []
    for q in cfg["queries"]:
        print(f"[fetch] {q['name']} ({q['location']})")
        try:
            jobs = fetch_jobs(
                rapid_key,
                query=q["query"],
                location=q["location"],
                remote=bool(q.get("remote")),
            )
        except Exception as e:  # noqa: BLE001 — one failed query shouldn't kill the night
            print(f"[warn] query '{q['name']}' failed: {e}")
            jobs = []
        all_jobs.extend(jobs)
    config.record_requests(needed)

    fresh = filter_new(all_jobs, seen)
    fresh = [j for j in fresh if _within_age(j, int(cfg.get("max_age_days", 7)))]
    print(f"[fetch] {len(all_jobs)} total, {len(fresh)} new after dedupe")

    if not fresh:
        print("[done] nothing new to score today.")
        _update_seen(seen, all_jobs, [])
        return 0

    top, scored_count = score_and_select(resume, fresh)
    stats = {
        "fetched": len(all_jobs),
        "new": len(fresh),
        "scored": scored_count,
        "requests_used": config.requests_used_this_month(),
        "budget": budget,
    }
    path = write_report(config.REPORTS_DIR, render(top, stats))
    print(f"[done] report written -> {path}")

    _update_seen(seen, all_jobs, top)
    return 0


def _update_seen(seen, all_jobs, top) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    scores = {job_hash(s.job): s.score for s in top}
    for job in all_jobs:
        h = job_hash(job)
        if h not in seen.entries:
            seen.entries[h] = SeenEntry(first_seen=today, score=scores.get(h, 0))
    config.prune_seen(seen)
    config.save_seen(seen)


if __name__ == "__main__":
    sys.exit(run())
