"""LLM scoring + cover letters via Pydantic AI (Gemini Flash).

Scoring forces a structured ScoreResult — numeric score, one-line reason —
so rankings are deterministic even though the model is not.
"""

import os
import time

from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from .models import Job, Resume, ScoreResult, ScoredJob

MODEL_NAMES = ["gemini-3.6-flash", "gemini-flash-lite-latest"]  # fallback = separate free-tier quota pool
MAX_SCORED_PER_RUN = 25  # free-tier reality: 60 calls cannot complete at 5 req/min
MAX_COVER_LETTERS = 5  # quota budget: letters only for the best matches
MIN_INTERVAL = 13.0  # Gemini free tier: 5 requests/minute per model
_last_call = 0.0


def _pace() -> None:
    global _last_call
    wait = _last_call + MIN_INTERVAL - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def _run_limited(build_agent, prompt: str):
    """Try each model in order; within a model, retry rate/transient errors."""
    last_err: Exception | None = None
    for name in MODEL_NAMES:
        for attempt in range(2):
            _pace()
            try:
                return build_agent(name).run_sync(prompt)
            except ModelHTTPError as e:
                last_err = e
                if e.status_code not in (429, 503):
                    raise
                time.sleep(15 * (attempt + 1))
    assert last_err
    raise last_err


def _api_key() -> str:
    key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("Set GEMINI_API_KEY (or GOOGLE_API_KEY) — see .env.example")
    return key


def _model(name: str) -> GoogleModel:
    return GoogleModel(name, provider=GoogleProvider(api_key=_api_key()))


def _score_agent(name: str) -> Agent:
    return Agent(
        _model(name),
        output_type=ScoreResult,
        instructions=(
            "You are a strict job-matching scorer. Score how well a job posting "
            "matches the candidate's resume. Be hard to please: 90+ only for near-"
            "perfect matches. Consider skills, seniority, location, and role title. "
            "The reason must be one line, max 160 characters."
        ),
    )


def _cover_agent(name: str) -> Agent:
    return Agent(
        _model(name),
        instructions=(
            "You write concise, honest cover letters (150-220 words) for job "
            "applications. Never invent experience: only use facts from the resume. "
            "Plain text, no markdown headers, addressed generically (no named "
            "recruiter). End with a single call-to-action sentence."
        ),
    )


def score_job(resume: Resume, job: Job) -> ScoreResult:
    prompt = f"""Resume (structured):
{resume.model_dump_json(indent=2)}

Job posting:
Title: {job.title}
Company: {job.company}
Location: {job.location} (remote={job.remote})
Posted: {job.posted_at}
Description:
{job.description}
"""
    result = _run_limited(_score_agent, prompt)
    return result.output


def draft_cover_letter(resume: Resume, job: Job) -> str:
    prompt = f"""Write a cover letter for this application.

Resume (structured):
{resume.model_dump_json(indent=2)}

Job posting:
Title: {job.title}
Company: {job.company}
Location: {job.location}
Description:
{job.description}
"""
    result = _run_limited(_cover_agent, prompt)
    return result.output


def score_and_select(resume: Resume, jobs: list[Job], top_n: int = 10) -> tuple[list[ScoredJob], int]:
    """Score jobs (capped), keep the top_n, draft cover letters for the best MAX_COVER_LETTERS."""
    scored: list[ScoredJob] = []
    for job in jobs[:MAX_SCORED_PER_RUN]:
        try:
            out = score_job(resume, job)
        except Exception as e:  # noqa: BLE001 — one bad job must not kill the run
            print(f"[warn] scoring failed for {job.company} — {job.title}: {e}")
            continue
        scored.append(ScoredJob(job=job, score=out.score, reason=out.reason))
        print(f"[score {out.score:3d}] {job.company} — {job.title}")

    scored.sort(key=lambda s: s.score, reverse=True)
    top = scored[:top_n]
    for i, s in enumerate(top):
        if i >= MAX_COVER_LETTERS:
            break
        try:
            s.cover_letter = draft_cover_letter(resume, s.job)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] cover letter failed for {s.job.company}: {e}")
            s.cover_letter = "(draft failed — apply manually)"
    return top, len(scored)
