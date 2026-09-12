#!/usr/bin/env python3
"""Convenience runner: python document_app.py --app "My App"  (no install needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dataverse_app_documentor.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
