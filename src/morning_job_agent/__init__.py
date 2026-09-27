import sys

# Job titles/descriptions can contain emoji; don't let the Windows console
# (cp1252) kill a run while printing them.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")

__version__ = "0.1.0"
