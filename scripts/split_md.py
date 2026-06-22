#!/usr/bin/env python3
"""Split memory.md / *REQUIREMENTS*.md into atomic units for classification.

Each heading, bullet item, or paragraph becomes one unit. A coarse heuristic
pre-tag (requirement / record / unknown) is attached as a *hint only* — the
final call is the model's, made by reading classification-guide.md.

Usage:
    split_md.py FILE [FILE ...] [--out units.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BULLET_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")

# Hint signals (generic, multilingual). Not authoritative.
REQ_SIGNALS = [
    "偏好", "规则", "禁止", "必须", "务必", "不要", "要求", "永久", "以后", "每次都",
    "always", "never", "must", "should", "do not", "don't", "preference", "rule",
]
REC_SIGNALS = [
    "本次", "本轮", "已处理", "保存为", "运行时间", "通知成功", "状态",
    "saved", "completed", "processed", "this run", "notified",
]
DATE_RE = re.compile(r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b|\b\d{8}\b|\d{1,2}:\d{2}")
# 运行专有的不透明 ID（长 token 含字母+数字混排），是 record 的强信号——通用，不绑定项目
OPAQUE_ID_RE = re.compile(r"\b[a-z]{1,4}[_-]?[0-9a-f]{8,}\b", re.I)


def is_heading(line: str) -> bool:
    return line.lstrip().startswith("#")


def is_bullet(line: str) -> bool:
    return bool(BULLET_RE.match(line))


def guess(text: str) -> str:
    low = text.lower()
    req = sum(1 for s in REQ_SIGNALS if s.lower() in low)
    rec = sum(1 for s in REC_SIGNALS if s.lower() in low)
    if DATE_RE.search(text):
        rec += 1
    if OPAQUE_ID_RE.search(text):
        rec += 1
    if req > rec:
        return "requirement"
    if rec > req:
        return "record"
    return "unknown"


def split_file(path: Path, start_id: int):
    lines = path.read_text(encoding="utf-8").splitlines()
    units = []
    heading = None
    i, n = 0, len(lines)
    uid = start_id

    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if is_heading(line):
            heading = line.strip("# ").strip()
            text = line.strip()
            units.append(_unit(uid, path, i + 1, i + 1, heading, text))
            uid += 1
            i += 1
            continue
        # bullet or paragraph: consume continuation (non-blank, non-heading,
        # non-new-bullet) lines
        start = i
        buf = [line]
        i += 1
        while i < n and lines[i].strip() and not is_heading(lines[i]) and not is_bullet(lines[i]):
            buf.append(lines[i])
            i += 1
        text = "\n".join(buf)
        units.append(_unit(uid, path, start + 1, i, heading, text))
        uid += 1
    return units, uid


def _unit(uid, path, l0, l1, heading, text):
    return {
        "id": f"u{uid:04d}",
        "source_file": str(path),
        "line_start": l0,
        "line_end": l1,
        "heading": heading,
        "text": text,
        "guess": guess(text),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", default="units.json")
    args = ap.parse_args()

    all_units = []
    uid = 1
    for f in args.files:
        p = Path(f)
        if not p.is_file():
            print(f"跳过（不存在）：{p}", file=sys.stderr)
            continue
        units, uid = split_file(p, uid)
        all_units.extend(units)

    Path(args.out).write_text(json.dumps(all_units, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {"requirement": 0, "record": 0, "unknown": 0}
    for u in all_units:
        counts[u["guess"]] += 1
    print(f"切分出 {len(all_units)} 个单元 → {args.out}")
    print(f"启发式预标（仅供参考）：requirement={counts['requirement']} "
          f"record={counts['record']} unknown={counts['unknown']}")
    print("请逐段阅读 units.json，依 references/classification-guide.md 判定，"
          "产出 classification.json。")


if __name__ == "__main__":
    main()
