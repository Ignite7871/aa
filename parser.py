#!/usr/bin/env python3
from __future__ import annotations
import os, json, re
from pathlib import Path
from typing import List, Optional

import yaml
import google.generativeai as genai

THIS_DIR = Path(__file__).parent
CFG = yaml.safe_load((THIS_DIR / "configs" / "settings.yml").read_text(encoding="utf-8"))


SYSTEM_RULES = """You are a command planner for a sandboxed terminal.
Return ONLY JSON with this schema:

{
  "commands": [
    ["mkdir","test"],
    ["mv","file1.txt","test/"],
    ["ls"]
  ]
}
"""

def _load_model():
    api_key = (CFG.get("gemini", {}) or {}).get("api_key") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Gemini API key missing. Put it in configs/settings.yml or set GEMINI_API_KEY.")
    genai.configure(api_key=api_key)
    model_name = (CFG.get("gemini", {}) or {}).get("model", "models/gemini-1.5-pro")
    return genai.GenerativeModel(model_name, system_instruction=SYSTEM_RULES)

# ----------------- Basic rule-based fallback -----------------
def _rule_based(nl: str) -> Optional[List[List[str]]]:
    """Very simple pattern-based fallback for common tasks."""
    text = nl.lower().strip()
    tokens = text.split()

    if text.startswith("make folder") or text.startswith("create folder"):
        # e.g. "make folder test"
        if len(tokens) >= 3:
            return [["mkdir", tokens[-1]]]

    if text.startswith("delete file"):
        # e.g. "delete file a.txt"
        if len(tokens) >= 3:
            return [["rm", tokens[-1]]]

    if text.startswith("show files") or text == "list files":
        return [["ls"]]

    if text.startswith("current dir") or text == "where am i":
        return [["pwd"]]

    return None

# ----------------- JSON helpers -----------------
def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        parts = s.split("```")
        if len(parts) >= 2:
            s = parts[1].lstrip()
            if s[:4].lower() == "json":
                s = s[4:].lstrip("\r\n")
    return s

def _find_outer_json(s: str) -> Optional[str]:
    start = s.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{": depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start:i+1]
    return None

def _extract_json(text: str) -> dict:
    s = _strip_fences(text)
    block = _find_outer_json(s) or "{}"
    return json.loads(block)

# ----------------- Main function -----------------
def nl_to_commands(nl: str, cwd_rel: str = "/", allowed: List[str] | None = None) -> List[List[str]]:
    """Turn natural-language instruction into a list of terminal commands."""
    allowed = allowed or (CFG.get("allowed_commands") or [])

    # 1. Try rule-based
    rb = _rule_based(nl)
    if rb:
        return rb

    # 2. Otherwise call Gemini
    model = _load_model()
    user = f"Current working directory: {cwd_rel}\nInstruction: {nl}\nReturn JSON only."
    resp = model.generate_content(
        [user],
        generation_config={
            "temperature": 0.05,
            "max_output_tokens": 256,
            "response_mime_type": "application/json",
        },
    )
    text = (resp.text or "").strip()
    if not text:
        return []

    try:
        data = _extract_json(text)
        cmds = data.get("commands", [])
        clean: List[List[str]] = []
        for entry in cmds:
            if isinstance(entry, list) and entry and entry[0] in allowed:
                clean.append([str(x) for x in entry])
        return clean
    except Exception:
        return []
