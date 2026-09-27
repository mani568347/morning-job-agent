"""Pydantic models shared across the pipeline."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Resume(BaseModel):
    full_name: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    titles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    years_experience: float = 0
    education: str = ""
    projects: list[str] = Field(default_factory=list)


class Job(BaseModel):
    id: str
    title: str
    company: str
    location: str
    url: str
    remote: bool = False
    posted_at: Optional[str] = None
    description: str = ""

    @field_validator("description")
    @classmethod
    def _clamp_description(cls, v: str) -> str:
        return v[:6000]


class ScoreResult(BaseModel):
    """Forced structured output from the scoring agent."""

    score: int = Field(ge=0, le=100, description="Match score vs the resume, 0-100")
    reason: str = Field(max_length=160, description="One line explaining the score")


class ScoredJob(BaseModel):
    job: Job
    score: int
    reason: str
    cover_letter: str = ""


class SeenEntry(BaseModel):
    first_seen: str
    score: int


class SeenStore(BaseModel):
    """hash -> entry. Hash = sha1(company|title|location), normalised."""

    entries: dict[str, SeenEntry] = Field(default_factory=dict)
