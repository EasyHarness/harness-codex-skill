#!/usr/bin/env python3
"""Safely replace the ``prompt`` field of a Codex automation.toml.

The model authors a restructured, deduped prompt (see references/toml-structure.md);
this script swaps just that field in — leaving every other byte untouched — then
round-trip validates that the parsed prompt matches what was intended, and prints
a unified diff. A timestamped backup is written before any change.

By default the prompt is written as a TOML multiline string (``\"\"\"...\"\"\"``)
so the file becomes human-readable; pass --style basic to keep the original
single-line escaped form.

Usage:
    restructure_toml.py --toml automation.toml --prompt-file new_prompt.txt [--apply] [--style multiline|basic]

Default is a dry run (prints the diff). Pass --apply to write.
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_toml, have_real_toml  # noqa: E402

KEY_RE = re.compile(r"(?m)^[ \t]*prompt[ \t]*=[ \t]*")


def find_prompt_span(text: str):
    """Return (value_start, value_end) covering the quoted prompt value."""
    m = KEY_RE.search(text)
    if not m:
        return None
    vs = m.end()
    if text.startswith('"""', vs):
        end = text.find('"""', vs + 3)
        if end == -1:
            return None
        return (vs, end + 3)
    if text[vs:vs + 1] == '"':
        i = vs + 1
        while i < len(text):
            c = text[i]
            if c == "\\":
                i += 2
                continue
            if c == '"':
                return (vs, i + 1)
            if c == "\n":
                return None
            i += 1
    return None


def to_basic(content: str) -> str:
    c = (content.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
                .replace("\t", "\\t")
                .replace("\r", ""))
    return f'"{c}"'


def to_multiline(content: str) -> str:
    c = content.replace("\\", "\\\\")
    c = c.replace('"""', '\\"\\"\\"')
    if c.endswith('"'):
        c = c[:-1] + '\\"'
    return '"""\n' + c + '\n"""'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--toml", required=True)
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--style", choices=["multiline", "basic"], default="multiline")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    toml_path = Path(args.toml)
    text = toml_path.read_text(encoding="utf-8")
    new_prompt = Path(args.prompt_file).read_text(encoding="utf-8").rstrip("\n")

    span = find_prompt_span(text)
    if span is None:
        sys.exit("找不到 prompt 字段（既非单行也非多行字符串）。请检查 toml。")

    serialized = to_multiline(new_prompt) if args.style == "multiline" else to_basic(new_prompt)
    new_text = text[:span[0]] + serialized + text[span[1]:]

    # Round-trip validation -------------------------------------------------
    try:
        parsed = load_toml(new_text)
    except Exception as e:
        sys.exit(f"生成的 TOML 解析失败，已中止：{e}")
    got = (parsed.get("prompt") or "").strip()
    want = new_prompt.strip()
    if got != want:
        sys.exit("校验失败：写回后解析得到的 prompt 与目标不一致，已中止（未改动文件）。\n"
                 f"  目标长度={len(want)} 实际长度={len(got)}")
    if not have_real_toml():
        print("提示：未检测到 tomllib/tomli，使用内置精简解析校验。"
              "如可能，建议用 python3.11+ 复核。", file=sys.stderr)

    diff = difflib.unified_diff(
        text.splitlines(keepends=True), new_text.splitlines(keepends=True),
        fromfile=str(toml_path), tofile=str(toml_path) + " (restructured)",
    )
    sys.stdout.writelines(diff)
    print()

    if not args.apply:
        print("[dry-run] 校验通过。加 --apply 才会备份并写回。")
        return

    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = toml_path.with_suffix(toml_path.suffix + f".bak.{ts}")
    backup.write_text(text, encoding="utf-8")
    toml_path.write_text(new_text, encoding="utf-8")
    print(f"已备份到 {backup}，并写回 {toml_path}。")


if __name__ == "__main__":
    main()
