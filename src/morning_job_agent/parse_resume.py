"""One-time resume parser: text/PDF -> data/resume.json.

Run locally, never in the nightly job:
    python -m morning_job_agent.parse_resume path/to/resume.pdf
"""

import sys

from pydantic import BaseModel

from . import config
from .models import Resume


class ResumeFields(BaseModel):
    """Constrained extraction output — the LLM fills this, we store it."""

    full_name: str = ""
    summary: str = ""
    skills: list[str] = []
    titles: list[str] = []
    locations: list[str] = []
    years_experience: float = 0
    education: str = ""
    projects: list[str] = []


def extract_text(path: str) -> str:
    if path.lower().endswith(".pdf"):
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    config.load_env()
    text = extract_text(sys.argv[1])
    if len(text.strip()) < 50:
        print("[error] could not extract readable text from that file")
        return 1

    from pydantic_ai import Agent

    from .scoring import _model, _run_limited

    agent_factory = lambda name: Agent(
        _model(name),
        output_type=ResumeFields,
        instructions=(
            "Extract structured facts from this resume. skills: concrete technical "
            "and tool skills. titles: job/role titles the candidate could apply for. "
            "locations: cities the candidate is open to working in (from explicit "
            "preferences, else their location). years_experience: total professional "
            "experience estimate. projects: one line each. Do not invent anything."
        ),
    )
    result = _run_limited(agent_factory, text[:20000])
    resume = Resume(**result.output.model_dump())

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.RESUME_JSON.write_text(resume.model_dump_json(indent=2), encoding="utf-8")
    print(f"[ok] wrote {config.RESUME_JSON}")
    print(resume.model_dump_json(indent=2))
    print("\nReview it — fix anything wrong in data/resume.json directly, then commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
