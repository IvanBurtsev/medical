#!/usr/bin/env python3
"""Точка входа MedAX Radar.

Примеры:
    python run.py run --competitors --export
    python run.py leads
    python run.py dashboard
    python run.py sources
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from medax_radar.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
