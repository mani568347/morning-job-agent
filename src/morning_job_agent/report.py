"""Renders reports/YYYY-MM-DD.md (IST date)."""

from datetime import datetime, timezone, timedelta
from pathlib import Path

from .models import ScoredJob

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> datetime:
    return datetime.now(timezone.utc).astimezone(IST)


def render(top: list[ScoredJob], stats: dict) -> str:
    now = _now_ist()
    lines = [
        f"# Morning Job Report — {now:%Y-%m-%d}",
        "",
        f"_Generated {now:%Y-%m-%d %H:%M} IST_",
        "",
        "| # | Score | Job | Company | Location | Reason |",
        "|---|-------|-----|---------|----------|--------|",
    ]
    for i, s in enumerate(top, 1):
        lines.append(
            f"| {i} | **{s.score}** | [{s.job.title}]({s.job.url}) | {s.job.company} "
            f"| {s.job.location} | {s.reason} |"
        )
    lines += [
        "",
        "## Stats",
        f"- Fetched: {stats['fetched']} | New after dedupe: {stats['new']} "
        f"| Scored successfully: {stats['scored']} | Shortlisted: {len(top)}",
        f"- JSearch requests this month: {stats['requests_used']} / {stats['budget']}",
        "",
        "---",
    ]
    for i, s in enumerate(top, 1):
        lines += [
            "",
            f"## {i}. {s.job.title} — {s.job.company} (score {s.score})",
            "",
            f"**Location:** {s.job.location}{' · Remote' if s.job.remote else ''}  ",
            f"**Apply:** {s.job.url}",
            "",
            "### Draft cover letter",
            "",
            s.cover_letter or "*(No draft this run — quota was spent scoring more jobs; apply directly.)*",
        ]
    return "\n".join(lines) + "\n"


def write_report(reports_dir: Path, content: str) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{_now_ist():%Y-%m-%d}.md"
    path.write_text(content, encoding="utf-8")
    return path
