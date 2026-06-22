"""Shared helpers for the harness-codex-skill scripts.

Dependency-free. Reads TOML via stdlib ``tomllib`` (Py3.11+) or ``tomli`` when
available, and otherwise falls back to a minimal parser that understands the
flat ``key = value`` shape Codex automation.toml files use (strings, multiline
strings, integers, and arrays of strings). Nothing here is project-specific.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# TOML loading
# ---------------------------------------------------------------------------

def _real_toml_loader():
    try:
        import tomllib  # py3.11+
        return tomllib.loads
    except ModuleNotFoundError:
        pass
    try:
        import tomli  # type: ignore
        return tomli.loads
    except ModuleNotFoundError:
        return None


def _unescape_basic(s: str) -> str:
    out = []
    i = 0
    simple = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "b": "\b", "f": "\f"}
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt in simple:
                out.append(simple[nxt])
                i += 2
                continue
            if nxt == "u" and i + 6 <= len(s):
                out.append(chr(int(s[i + 2:i + 6], 16)))
                i += 6
                continue
            if nxt == "U" and i + 10 <= len(s):
                out.append(chr(int(s[i + 2:i + 10], 16)))
                i += 10
                continue
        out.append(c)
        i += 1
    return "".join(out)


def _mini_parse(text: str) -> dict:
    """Best-effort parser for flat Codex automation.toml files."""
    data: dict = {}
    i = 0
    n = len(text)
    key_re = re.compile(r"[ \t]*([A-Za-z0-9_-]+)[ \t]*=[ \t]*")
    while i < n:
        # skip whitespace / comments / blank lines
        line_end = text.find("\n", i)
        if line_end == -1:
            line_end = n
        line = text[i:line_end]
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("["):
            i = line_end + 1
            continue
        m = key_re.match(line)
        if not m:
            i = line_end + 1
            continue
        key = m.group(1)
        vstart = i + m.end()
        if text.startswith('"""', vstart):
            end = text.find('"""', vstart + 3)
            raw = text[vstart + 3:end]
            if raw.startswith("\n"):
                raw = raw[1:]
            data[key] = _unescape_basic(raw)
            i = end + 3
        elif text[vstart:vstart + 1] == '"':
            j = vstart + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    break
                j += 1
            data[key] = _unescape_basic(text[vstart + 1:j])
            i = j + 1
        elif text[vstart:vstart + 1] == "[":
            end = text.find("]", vstart)
            inner = text[vstart + 1:end]
            data[key] = [
                _unescape_basic(x.strip().strip('"'))
                for x in inner.split(",")
                if x.strip()
            ]
            i = end + 1
        else:
            val = text[vstart:line_end].strip()
            try:
                data[key] = int(val)
            except ValueError:
                data[key] = val.strip('"')
            i = line_end + 1
        # advance past trailing newline
        if i < n and text[i:i + 1] == "\n":
            i += 1
    return data


def load_toml(text: str) -> dict:
    loader = _real_toml_loader()
    if loader is not None:
        return loader(text)
    return _mini_parse(text)


def have_real_toml() -> bool:
    return _real_toml_loader() is not None


# ---------------------------------------------------------------------------
# Locating the official automation.toml for a working directory
# ---------------------------------------------------------------------------

def find_automation_tomls(workdir: Path) -> list[dict]:
    """Return automation.toml files under ~/.codex/automations whose ``cwds``
    contain (or equal) ``workdir``."""
    workdir = Path(workdir).resolve()
    base = Path.home() / ".codex" / "automations"
    matches: list[dict] = []
    if not base.is_dir():
        return matches
    for tp in sorted(base.glob("*/automation.toml")):
        try:
            data = load_toml(tp.read_text(encoding="utf-8"))
        except Exception:
            continue
        cwds = data.get("cwds") or []
        if isinstance(cwds, str):
            cwds = [cwds]
        for c in cwds:
            try:
                cp = Path(c).resolve()
            except Exception:
                continue
            if cp == workdir or _is_within(workdir, cp) or _is_within(cp, workdir):
                matches.append({
                    "toml": str(tp),
                    "id": data.get("id", tp.parent.name),
                    "name": data.get("name", ""),
                    "cwd": c,
                })
                break
    return matches


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Sizes / formatting
# ---------------------------------------------------------------------------

def path_size(p: Path) -> int:
    p = Path(p)
    if p.is_symlink():
        return 0
    if p.is_file():
        try:
            return p.stat().st_size
        except OSError:
            return 0
    total = 0
    for root, _dirs, files in os.walk(p):
        for f in files:
            fp = Path(root) / f
            try:
                if not fp.is_symlink():
                    total += fp.stat().st_size
            except OSError:
                pass
    return total


def human_size(num: int) -> str:
    f = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.0f}{unit}" if unit == "B" else f"{f:.1f}{unit}"
        f /= 1024
    return f"{f:.1f}TB"
