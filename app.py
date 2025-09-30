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

# ----------------------- Setup -----------------------
st.set_page_config(page_title=" Terminal – Streamlit", page_icon="💻", layout="wide")
ROOT = Path(__file__).parent.resolve()

# Create single Terminal instance per session
if "term" not in st.session_state:
    st.session_state.term = Terminal(ROOT)
    buf = io.StringIO()
    with redirect_stdout(buf):
        st.session_state.term._banner()
    st.session_state.feed: List[str] = [buf.getvalue().rstrip("\n")]
    st.session_state.show_plan: List[str] = []

term: Terminal = st.session_state.term

# ----------------------- Helpers -----------------------
def exec_line_and_capture(line: str) -> str:
    out = io.StringIO()
    with redirect_stdout(out):
        try:
            term.execute(line)
        except SystemExit:
            print("exit")
        except Exception as e:
            print(f"error: {e}")
    return out.getvalue()

try:
    rel = str(term.cwd.relative_to(term.root)) if term.cwd != term.root else "/"
except Exception:
    rel = "/"

# ----------------------- UI -----------------------
left, right = st.columns([2, 1])

with left:
    st.markdown("## Terminal – Streamlit UI")
    st.caption("Interactive Python terminal with AI assist and history.")

    # Output window styled like first version
    out_container = st.container(border=True)
    with out_container:
        for chunk in st.session_state.feed[-200:]:
            st.markdown(chunk, unsafe_allow_html=True)

    # Input row
    st.write("")
    with st.form("cmd_form", clear_on_submit=True):
        ai_mode = st.toggle("AI Assist", value=False, help="Use natural language → planned commands → execute")
        user_line = st.text_input(
            "Command",
            placeholder="e.g., ls, pwd, mkdir demo, cd demo, touch a.txt",
        )
        c1, c2, c3 = st.columns([1, 1, 6])
        run_btn = c1.form_submit_button("Run", type="primary", use_container_width=True)
        dry_run = c2.checkbox("Dry run", value=False, help="Plan but do not actually change files (AI mode)")
        clear_btn = c3.form_submit_button("Clear Output", use_container_width=False)

    if clear_btn:
        buf = io.StringIO()
        with redirect_stdout(buf):
            term._banner()
        st.session_state.feed = [buf.getvalue().rstrip("\n")]
        st.session_state.show_plan = []
        st.rerun()

    if run_btn and user_line.strip():
        line = user_line.strip()

        if not ai_mode:
            out = exec_line_and_capture(line)
            st.session_state.feed.append(f"`$ {line}`")
            st.session_state.feed.append(f"```bash\n{out.rstrip()}\n```")
            append_history(line)
            st.rerun()
        else:
            try:
                with st.spinner("Thinking…"):
                    planned = nl_to_commands(line, cwd_rel=rel)
                st.session_state.show_plan = ["$ " + " ".join(cmd) for cmd in planned] if planned else ["(no commands)"]
                plan_block = "\n".join(st.session_state.show_plan)
                st.session_state.feed.append(f"`$ # NL: {line}`")
                st.session_state.feed.append(f"```bash\nPlanned:\n{plan_block}\n```")

                if planned and not dry_run:
                    _, output = run_commands(term, planned, dry_run=False)
                    st.session_state.feed.append(f"```bash\n{output.rstrip()}\n```")
                    append_history(f"# NL: {line}")
                    for c in planned:
                        append_history(" ".join(c))
                elif planned and dry_run:
                    append_history(f"# NL (dry): {line}")
                    for c in planned:
                        append_history(" ".join(c))
            except Exception as e:
                st.session_state.feed.append(f"error: {e}")
            st.rerun()

with right:
    st.markdown("### Quick Actions")
    c1, c2 = st.columns(2)
    if c1.button("pwd", use_container_width=True):
        out = exec_line_and_capture("pwd")
        st.session_state.feed.append("`$ pwd`")
        st.session_state.feed.append(f"```bash\n{out.rstrip()}\n```")
        append_history("pwd"); st.rerun()
    if c2.button("ls", use_container_width=True):
        out = exec_line_and_capture("ls")
        st.session_state.feed.append("`$ ls`")
        st.session_state.feed.append(f"```bash\n{out.rstrip()}\n```")
        append_history("ls"); st.rerun()

    c3, c4 = st.columns(2)
    if c3.button("sysmon", use_container_width=True):
        out = exec_line_and_capture("sysmon")
        st.session_state.feed.append("`$ sysmon`")
        st.session_state.feed.append(f"```bash\n{out.rstrip()}\n```")
        append_history("sysmon"); st.rerun()
    if c4.button("df", use_container_width=True):
        out = exec_line_and_capture("df")
        st.session_state.feed.append("`$ df`")
        st.session_state.feed.append(f"```bash\n{out.rstrip()}\n```")
        append_history("df"); st.rerun()

    st.divider()
    st.markdown("### Recent History")
    for line in load_last(15):
        st.code(line, language="bash")

    st.caption(f"cwd: {rel}")
