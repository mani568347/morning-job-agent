"""Paths, environment, and the persistent stores (seen jobs + request budget)."""

import json
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .models import Resume, SeenStore

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"

RESUME_JSON = DATA_DIR / "resume.json"
SEEN_JSON = DATA_DIR / "seen.json"
USAGE_JSON = DATA_DIR / "usage.json"


def load_env() -> None:
    load_dotenv(ROOT / ".env")


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable {name} (see .env.example)")
    return value


def load_queries_config() -> dict:
    with open(CONFIG_DIR / "queries.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not cfg.get("queries"):
        raise RuntimeError("config/queries.yaml has no queries")
    return cfg


def load_resume() -> Resume:
    if not RESUME_JSON.exists():
        raise RuntimeError(
            "data/resume.json not found — run: python -m morning_job_agent.parse_resume <resume.pdf|txt>"
        )
    return Resume.model_validate_json(RESUME_JSON.read_text(encoding="utf-8"))


def load_seen() -> SeenStore:
    if SEEN_JSON.exists():
        return SeenStore.model_validate(json.loads(SEEN_JSON.read_text(encoding="utf-8")))
    return SeenStore()


def save_seen(store: SeenStore) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SEEN_JSON.write_text(store.model_dump_json(indent=2), encoding="utf-8")


def current_month() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m")


def load_usage() -> dict:
    if USAGE_JSON.exists():
        return json.loads(USAGE_JSON.read_text(encoding="utf-8"))
    return {}


def save_usage(usage: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    USAGE_JSON.write_text(json.dumps(usage, indent=2), encoding="utf-8")


def record_requests(n: int) -> int:
    """Add n to this month's counter and return the new total."""
    usage = load_usage()
    month = current_month()
    total = usage.get(month, 0) + n
    usage[month] = total
    save_usage(usage)
    return total


def requests_used_this_month() -> int:
    return load_usage().get(current_month(), 0)


def prune_seen(store: SeenStore, keep_days: int = 60) -> SeenStore:
    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).date().isoformat()
    store.entries = {k: v for k, v in store.entries.items() if v.first_seen >= cutoff}
    return store
