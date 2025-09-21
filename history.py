#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(exist_ok=True, parents=True)

# Keep file name as in your screenshot (typo preserved for compatibility)
HIST_FILE = OUT_DIR / "histroy_backup.txt"

def append_history(line: str) -> None:
    HIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HIST_FILE, "a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")

def load_last(n: int = 100) -> list[str]:
    if not HIST_FILE.exists():
        return []
    lines = HIST_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
    return lines[-n:]
