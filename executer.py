#!/usr/bin/env python3
from __future__ import annotations
import io
from contextlib import redirect_stdout
from typing import List, Tuple

from main import Terminal  # reuses your CLI backend

def run_commands(term: Terminal, plan: List[List[str]], dry_run: bool = False) -> Tuple[str, str]:
    """
    Execute commands like: [["mkdir","test"], ["mv","a.txt","test/"]]
    Returns (printed_plan, combined_output)
    """
    plan_text = "\n".join("$ " + " ".join(map(str, cmd)) for cmd in plan)
    if dry_run:
        return (plan_text, "(dry run)")
    buf = io.StringIO()
    with redirect_stdout(buf):
        for cmd in plan:
            try:
                line = " ".join(map(str, cmd))
                print(f"$ {line}")
                term.execute(line)
            except SystemExit:
                print("exit")
            except Exception as e:
                print(f"error: {e}")
    return (plan_text, buf.getvalue())
