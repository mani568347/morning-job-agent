"""Deduplication on sha1(company|title|location).

Without this the same posting shows up for a week straight across boards.
"""

import hashlib
import re

from .models import Job, SeenStore

_WORD = re.compile(r"[a-z0-9]+")


def normalize(text: str) -> str:
    return " ".join(_WORD.findall(text.lower()))


def job_hash(job: Job) -> str:
    key = "|".join(normalize(x) for x in (job.company, job.title, job.location))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def filter_new(jobs: list[Job], seen: SeenStore) -> list[Job]:
    """Return jobs never seen before, preserving order, itself deduped in-run."""
    fresh: list[Job] = []
    batch: set[str] = set()
    for job in jobs:
        h = job_hash(job)
        if h in seen.entries or h in batch:
            continue
        batch.add(h)
        fresh.append(job)
    return fresh
