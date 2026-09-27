"""JSearch (RapidAPI) client. One HTTP request per saved query."""

import time
import uuid
from typing import Optional

import httpx

from .models import Job

BASE_URL = "https://jsearch.p.rapidapi.com/search-v2"


def fetch_jobs(
    rapid_api_key: str,
    query: str,
    location: str,
    remote: bool = False,
    num_jobs: int = 30,
    page: int = 1,
) -> list[Job]:
    params = {
        "query": f"{query} remote" if remote else query,
        "location": location,
        "page": str(page),
        "num_jobs": str(num_jobs),
        "date_posted": "week",
    }
    headers = {
        "x-rapidapi-key": rapid_api_key,
        "x-rapidapi-host": "jsearch.p.rapidapi.com",
    }
    for attempt in range(3):
        try:
            resp = httpx.get(BASE_URL, params=params, headers=headers, timeout=30)
            if resp.status_code == 429:
                # Rate limited — back off once, then give up on this query.
                time.sleep(3 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            break
        except httpx.HTTPError:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    else:
        return []

    jobs: list[Job] = []
    for item in (data.get("data") or {}).get("jobs") or []:
        job = _parse(item)
        if job:
            jobs.append(job)
    return jobs


def _parse(item: dict) -> Optional[Job]:
    title = (item.get("job_title") or "").strip()
    company = (item.get("employer_name") or "").strip()
    url = (item.get("job_apply_link") or item.get("job_google_link") or "").strip()
    if not title or not company or not url:
        return None
    location = ", ".join(
        str(p) for p in (item.get("job_city"), item.get("job_state"), item.get("job_country")) if p
    )
    description = item.get("job_description") or ""
    # Some JSearch results are hydrated (description present), others are stubs.
    snippet = " ".join(item.get("job_highlights", {}).get("Qualifications", [])[:5])
    return Job(
        id=item.get("job_id") or uuid.uuid4().hex,
        title=title,
        company=company,
        location=location or "Not specified",
        url=url,
        remote=bool(item.get("job_is_remote")),
        posted_at=item.get("job_posted_at_datetime_utc"),
        description=description or snippet,
    )
