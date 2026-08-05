"""Backward-compatible thin launcher for ``python -m rulemerger``."""

from rulemerger.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
