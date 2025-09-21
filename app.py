#!/usr/bin/env python3
from __future__ import annotations
import io
from contextlib import redirect_stdout
from pathlib import Path
from typing import List
import streamlit as st

from main import Terminal
from parser import nl_to_commands
from executer import run_commands
from history import append_history, load_last

st.set_page_config(page_title="CodeMate Terminal", page_icon="💻", layout="wide")
ROOT = Path(__file__).parent.resolve()

# ---------- Session bootstrap ----------
if "term" not in st.session_state:
    st.session_state.term = Terminal(ROOT)
    # capture banner once
    buf = io.StringIO()
    with redirect_stdout(buf):
        st.session_state.term._banner()
    # terminal feed (list[str]), each item already includes $ prompt and output
    st.session_state.feed: List[str] = [buf.getvalue().rstrip("\n")]
    st.session_state.show_plan: List[str] = []  # planned commands preview

term: Terminal = st.session_state.term

def exec_line_and_capture(line: str) -> str:
    """Execute a single line through Terminal backend and capture stdout."""
    out = io.StringIO()
    with redirect_stdout(out):
        try:
            term.execute(line)
        except SystemExit:
            print("exit")
        except Exception as e:
            print(f"error: {e}")
    return out.getvalue()

# ---------- Layout: terminal-like UI ----------
st.markdown(
    """
    <style>
    .term-wrap {background:#0b1020;border-radius:12px;padding:12px;height:70vh;overflow:auto;
                box-shadow:0 10px 30px rgba(0,0,0,.25);}
    .term-line {white-space:pre-wrap;font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
                color:#e6ebff;margin:0 0 .4rem;}
    .term-line .prompt{color:#7aa2ff;}
    .muted{color:#9aa3c7;}
    .planned {background:#0e1530;border-radius:8px;padding:8px;margin:8px 0;}
    </style>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns([3, 1], gap="large")

with left:
    st.markdown("#### CodeMate Terminal")
    # feed
    feed_container = st.container()
    with feed_container:
        for chunk in st.session_state.feed[-200:]:
            st.markdown(f"<div class='term-line'>{chunk}</div>", unsafe_allow_html=True)

    # input row
    with st.form("cmd_form", clear_on_submit=True):
        # Show current rel cwd in prompt
        try:
            rel = str(term.cwd.relative_to(term.root)) if term.cwd != term.root else "/"
        except Exception:
            rel = "/"
        ai_mode = st.toggle("AI Assist", value=False, help="Use natural language → planned commands → execute")
        user_line = st.text_input(
            label="",
            placeholder="Type a command (e.g., ls) or a natural language instruction in AI mode",
            label_visibility="collapsed",
        )
        c1, c2, c3 = st.columns([1, 1, 6])
        run_btn = c1.form_submit_button("Run", type="primary", use_container_width=True)
        dry_run = c2.checkbox("Dry run", value=False, help="Plan but do not actually change files (AI mode)")
        clear_btn = c3.form_submit_button("Clear Output", use_container_width=False)

    if clear_btn:
        st.session_state.feed = []
        st.session_state.show_plan = []
        st.rerun()

    # Handle Run
    if run_btn and user_line.strip():
        line = user_line.strip()

        if not ai_mode:
            # plain terminal mode
            out = exec_line_and_capture(line)
            st.session_state.feed.append(f"<span class='prompt'>$</span> {line}")
            st.session_state.feed.append(out.rstrip("\n"))
            append_history(line)
            st.rerun()
        else:
            # AI mode: NL → commands → (optional) execute
            try:
                with st.spinner("Thinking…"):
                    planned = nl_to_commands(line, cwd_rel=rel)
                st.session_state.show_plan = ["$ " + " ".join(cmd) for cmd in planned] if planned else ["(no commands)"]
                plan_block = "\n".join(st.session_state.show_plan)
                st.session_state.feed.append(f"<span class='prompt'>$</span> # NL: {line}")
                st.session_state.feed.append(f"<div class='planned'><span class='muted'>Planned:</span>\n{plan_block}</div>")

                if planned and not dry_run:
                    _, output = run_commands(term, planned, dry_run=False)
                    # run_commands already echoes `$ command` lines; just append
                    st.session_state.feed.append(output.rstrip("\n"))
                    append_history(f"# NL: {line}")
                    for c in planned:
                        append_history(" ".join(c))
                elif planned and dry_run:
                    # show plan only
                    append_history(f"# NL (dry): {line}")
                    for c in planned:
                        append_history(" ".join(c))
            except Exception as e:
                st.session_state.feed.append(f"error: {e}")

            st.rerun()

with right:
    st.markdown("#### Quick Actions")
    c1, c2 = st.columns(2)
    if c1.button("pwd", use_container_width=True):
        out = exec_line_and_capture("pwd")
        st.session_state.feed.append("<span class='prompt'>$</span> pwd")
        st.session_state.feed.append(out.rstrip("\n")); append_history("pwd"); st.rerun()
    if c2.button("ls", use_container_width=True):
        out = exec_line_and_capture("ls")
        st.session_state.feed.append("<span class='prompt'>$</span> ls")
        st.session_state.feed.append(out.rstrip("\n")); append_history("ls"); st.rerun()

    c3, c4 = st.columns(2)
    if c3.button("sysmon", use_container_width=True):
        out = exec_line_and_capture("sysmon")
        st.session_state.feed.append("<span class='prompt'>$</span> sysmon")
        st.session_state.feed.append(out.rstrip("\n")); append_history("sysmon"); st.rerun()
    if c4.button("df", use_container_width=True):
        out = exec_line_and_capture("df")
        st.session_state.feed.append("<span class='prompt'>$</span> df")
        st.session_state.feed.append(out.rstrip("\n")); append_history("df"); st.rerun()

    st.markdown("#### Recent History")
    for line in load_last(15):
        st.code(line, language="bash")
