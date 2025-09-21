#!/usr/bin/env python3
"""
Problem 1: Python-Based Command Terminal
- REPL + core commands
- Error handling
- System monitors
- Sandboxed to project root
- NEW: persistent history file + simple tab completion
"""
from __future__ import annotations
import os, sys, shlex, shutil, platform, subprocess, glob
from pathlib import Path
from datetime import datetime

# Optional readline
try:
    import readline  # pyreadline3 on Windows via requirements
except Exception:
    readline = None

from history import append_history  # persistent backup

class Terminal:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.cwd = self.root
        self.commands = {
            'help': self.cmd_help,
            'pwd': self.cmd_pwd,
            'ls': self.cmd_ls,
            'cd': self.cmd_cd,
            'mkdir': self.cmd_mkdir,
            'rm': self.cmd_rm,
            'touch': self.cmd_touch,
            'cat': self.cmd_cat,
            'echo': self.cmd_echo,
            'cp': self.cmd_cp,
            'mv': self.cmd_mv,
            'head': self.cmd_head,
            'tail': self.cmd_tail,
            'ps': self.cmd_ps,
            'sysmon': self.cmd_sysmon,
            'df': self.cmd_df,
            'history': self.cmd_history,
            'exit': self.cmd_exit,
            'quit': self.cmd_exit,
        }
        self._ensure_root_exists()
        self._init_readline()

    # ---------- setup ----------
    def _ensure_root_exists(self):
        self.root.mkdir(parents=True, exist_ok=True)

    def _init_readline(self):
        if not readline:
            return
        try:
            histfile = str(self.root / '.terminal_history')
            try:
                readline.read_history_file(histfile)
            except Exception:
                pass
            import atexit
            atexit.register(lambda: self._save_history(histfile))
            # tab completion
            def complete_fn(text, state):
                # First token → command names
                buf = readline.get_line_buffer()
                parts = shlex.split(buf, posix=True) if buf.strip() else []
                if len(parts) <= 1 and not buf.endswith(' '):
                    opts = [c for c in self.commands.keys() if c.startswith(text)]
                    return (opts + [None])[state]
                # Else: path/file completion relative to cwd
                pattern = text + '*'
                g = glob.glob(str(self.cwd / pattern))
                # map absolute -> relative names
                rels = []
                for p in g:
                    name = os.path.relpath(p, start=str(self.cwd))
                    if os.path.isdir(p):
                        name = name + os.sep
                    if name.startswith('./'):
                        name = name[2:]
                    rels.append(name)
                opts = sorted(set(rels))
                return (opts + [None])[state]
            readline.set_completer_delims(' \t\n')
            readline.parse_and_bind('tab: complete')
            readline.set_completer(complete_fn)
        except Exception:
            pass

    def _save_history(self, histfile: str):
        if readline:
            try:
                readline.write_history_file(histfile)
            except Exception:
                pass

    def _resolve_path(self, path_str: str | None) -> Path:
        if not path_str:
            return self.cwd
        p = Path(path_str)
        p = (self.cwd / p).resolve() if not p.is_absolute() else p.resolve()
        try:
            p.relative_to(self.root)
        except ValueError:
            p = (self.root / p.name).resolve()
        return p

    def _print_err(self, msg: str): print(f"error: {msg}")
    def _confirm(self, prompt: str) -> bool:
        try: return input(f"{prompt} [y/N]: ").strip().lower() == 'y'
        except EOFError: return False

    # ---------- REPL ----------
    def run(self):
        self._banner()
        while True:
            try:
                rel = str(self.cwd.relative_to(self.root)) if self.cwd != self.root else ''
                line = input(f"codemate:{rel if rel else '/'}$ ")
            except (EOFError, KeyboardInterrupt):
                print("\nexit"); break
            if not line.strip():
                continue
            append_history(line)  # persist
            self.execute(line)

    def execute(self, line: str):
        try:
            parts = shlex.split(line)
        except ValueError as e:
            self._print_err(f"parse error: {e}"); return
        cmd, *args = parts
        fn = self.commands.get(cmd)
        if not fn:
            self._print_err(f"unknown command: {cmd}. Try 'help'."); return
        try:
            fn(args)
        except SystemExit: raise
        except Exception as e: self._print_err(str(e))

    # ---------- commands ----------
    def cmd_help(self, args):
        print("""Built-in commands:
  help  pwd  ls  cd  mkdir  rm  touch  cat  echo
  cp  mv  head  tail  ps  sysmon  df  history  exit|quit
        """.strip())

    def cmd_pwd(self, args): print(str(self.cwd))
    def cmd_ls(self, args):
        show_all, target = False, None
        for a in args:
            if a == '-a': show_all = True
            else: target = a
        path = self._resolve_path(target)
        if not path.exists(): self._print_err("path not found"); return
        if path.is_file(): print(path.name); return
        items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        for p in items:
            if not show_all and p.name.startswith('.'): continue
            print(p.name + ('/' if p.is_dir() else ''))

    def cmd_cd(self, args):
        path = self._resolve_path(args[0]) if args else self.root
        if not path.exists() or not path.is_dir(): self._print_err("no such directory"); return
        try: path.relative_to(self.root)
        except ValueError: self._print_err("access outside project root is blocked"); return
        self.cwd = path

    def cmd_mkdir(self, args):
        if not args: self._print_err("usage: mkdir <dir>..."); return
        for d in args: Path(self._resolve_path(d)).mkdir(parents=True, exist_ok=True)

    def cmd_rm(self, args):
        if not args: self._print_err("usage: rm [-r] <path>..."); return
        recursive, paths = False, []
        for a in args:
            if a == '-r': recursive = True
            else: paths.append(a)
        for pstr in paths:
            p = self._resolve_path(pstr)
            if not p.exists(): self._print_err(f"not found: {pstr}"); continue
            if p.is_dir():
                if not recursive: self._print_err(f"is a directory (use -r): {pstr}"); continue
                if not self._confirm(f"rm -r {p}"): print("aborted"); continue
                shutil.rmtree(p)
            else: p.unlink()

    def cmd_touch(self, args):
        if not args: self._print_err("usage: touch <file>..."); return
        for f in args:
            p = self._resolve_path(f); p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, 'a', encoding='utf-8'): os.utime(p, None)

    def cmd_cat(self, args):
        if not args: self._print_err("usage: cat <file>..."); return
        for f in args:
            p = self._resolve_path(f)
            if not p.exists() or not p.is_file(): self._print_err(f"no such file: {f}"); continue
            print(p.read_text(encoding='utf-8', errors='replace'), end='')

    def cmd_echo(self, args): print(' '.join(args))

    def cmd_cp(self, args):
        if len(args) < 2: self._print_err("usage: cp <src> <dst>"); return
        src, dst = self._resolve_path(args[0]), self._resolve_path(args[1])
        if not src.exists(): self._print_err("source not found"); return
        if src.is_dir():
            if dst.exists() and dst.is_dir(): dst = dst / src.name
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            if dst.is_dir(): dst = dst / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    def cmd_mv(self, args):
        if len(args) < 2: self._print_err("usage: mv <src> <dst>"); return
        src, dst = self._resolve_path(args[0]), self._resolve_path(args[1])
        if not src.exists(): self._print_err("source not found"); return
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(src), str(dst))

    def _read_n_lines(self, path: Path, n: int, tail: bool = False):
        if n <= 0: return
        if tail:
            from collections import deque
            dq = deque(maxlen=n)
            with open(path, 'r', encoding='utf-8', errors='replace') as fh:
                for line in fh: dq.append(line)
            for line in dq: print(line, end='')
        else:
            with open(path, 'r', encoding='utf-8', errors='replace') as fh:
                for i, line in enumerate(fh):
                    if i >= n: break
                    print(line, end='')

    def cmd_head(self, args):
        if not args: self._print_err("usage: head [-n N] <file>"); return
        n, files, it = 10, [], iter(args)
        for a in it:
            if a == '-n':
                try: n = int(next(it))
                except Exception: self._print_err("invalid N"); return
            else: files.append(a)
        for f in files:
            p = self._resolve_path(f)
            if not p.exists() or not p.is_file(): self._print_err(f"no such file: {f}"); continue
            self._read_n_lines(p, n, tail=False)

    def cmd_tail(self, args):
        if not args: self._print_err("usage: tail [-n N] <file>"); return
        n, files, it = 10, [], iter(args)
        for a in it:
            if a == '-n':
                try: n = int(next(it))
                except Exception: self._print_err("invalid N"); return
            else: files.append(a)
        for f in files:
            p = self._resolve_path(f)
            if not p.exists() or not p.is_file(): self._print_err(f"no such file: {f}"); continue
            self._read_n_lines(p, n, tail=True)

    def cmd_ps(self, args):
        try:
            if platform.system() == 'Windows': subprocess.run(["tasklist"], check=False)
            else: subprocess.run(["ps","-e","-o","pid,comm,pcpu,pmem"], check=False)
        except Exception as e: self._print_err(f"ps failed: {e}")

    def cmd_sysmon(self, args):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S'); print(f"Snapshot @ {now}")
        if hasattr(os, 'getloadavg'):
            try: la1, la5, la15 = os.getloadavg(); print(f"loadavg: 1m={la1:.2f} 5m={la5:.2f} 15m={la15:.2f}")
            except Exception: pass
        try:
            if platform.system() == 'Linux':
                with open('/proc/meminfo','r',encoding='utf-8',errors='ignore') as fh:
                    for _ in range(5): print(next(fh).strip())
            elif platform.system() == 'Darwin': subprocess.run(["vm_stat"], check=False)
            elif platform.system() == 'Windows':
                subprocess.run(["wmic","OS","get","FreePhysicalMemory,TotalVisibleMemorySize","/Value"], check=False)
        except Exception as e: self._print_err(f"mem info failed: {e}")

    def cmd_df(self, args):
        total, used, free = shutil.disk_usage(self.root)
        gb = lambda x: x/(1024**3)
        print(f"Filesystem (project root): total={gb(total):.2f}G used={gb(used):.2f}G free={gb(free):.2f}G")

    def cmd_history(self, args):
        if not readline:
            print("history unavailable on this platform"); return
        hist_len = readline.get_current_history_length()
        start = max(1, hist_len - 50 + 1)
        for i in range(start, hist_len + 1):
            print(f"{i}: {readline.get_history_item(i)}")

    def cmd_exit(self, args): raise SystemExit(0)

    def _banner(self):
        print("CodeMate Python Terminal (sandboxed)\nType 'help' to see commands, 'exit' to leave.")

def main():
    root = Path(__file__).parent
    term = Terminal(root)
    term.run()

if __name__ == '__main__':
    try: main()
    except SystemExit as e: sys.exit(e.code)
    except Exception as e: print(f"fatal: {e}"); sys.exit(1)
