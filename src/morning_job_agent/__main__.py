import sys

from .pipeline import run

try:
    sys.exit(run())
except RuntimeError as e:
    print(f"[error] {e}", file=sys.stderr)
    sys.exit(1)
