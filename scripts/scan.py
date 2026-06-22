#!/usr/bin/env python3
"""Inventory and classify Codex automation artifacts in a working directory.

Generic: classification is by *structural traits*, never by project-specific
names. Detects duplicate runtime environments (keeps one, flags the rest as
redundant), caches, temp/snapshot state, root-level leaked data dumps, and junk
— while protecting deliverables, dedup state, logs, and rule/memory sources.

Usage:
    scan.py WORKDIR [--out inventory.json] [--toml PATH]

Writes a machine-readable inventory.json and prints a human Markdown report.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    find_automation_tomls,
    human_size,
    path_size,
)

# Category -> default action ("keep" | "quarantine")
DEFAULT_ACTION = {
    "env-keep": "keep",
    "redundant-env": "quarantine",
    "env-node": "keep",          # regenerable but per-project; user decides
    "cache": "quarantine",
    "temp-state": "quarantine",
    "leaked-output": "quarantine",
    "misc-junk": "quarantine",
    "deliverable": "keep",
    "dedup-state": "keep",
    "rule-source": "keep",
    "log": "keep",
    "other": "keep",
}

CONSERVATIVE_QUARANTINE = ["redundant-env", "cache", "temp-state", "leaked-output", "misc-junk"]

# Directory names handled as a single unit (not descended into)
PRUNE_ALWAYS = {".git", ".hg", ".svn"}


def is_env_dir(p: Path) -> bool:
    return (p / "pyvenv.cfg").exists() or (p / "bin" / "activate").exists()


def make_entry(workdir: Path, p: Path, category, group=None, reason="", action=None):
    p = Path(p)
    return {
        "path": str(p),
        "rel": str(p.relative_to(workdir)) if _within(p, workdir) else str(p),
        "category": category,
        "group": group,
        "size": path_size(p),
        "is_dir": p.is_dir(),
        "action": action or DEFAULT_ACTION.get(category, "keep"),
        "reason": reason,
    }


def _within(p: Path, base: Path) -> bool:
    try:
        p.relative_to(base)
        return True
    except ValueError:
        return False


def classify_file(workdir: Path, p: Path):
    name = p.name
    low = name.lower()
    at_root = p.parent.resolve() == workdir.resolve()

    if name == ".DS_Store" or low == "thumbs.db":
        return ("misc-junk", "系统/目录元数据，可再生")
    if low.endswith((".pyc", ".pyo")):
        return ("cache", "编译缓存，可再生")
    if re.search(r"run-?log", low) and low.endswith(".md"):
        return ("log", "运行日志，可后续归档")
    if re.search(r"run-?report", low) and low.endswith(".md"):
        return ("log", "运行报告，可后续归档")
    if low == "memory.md" or (low.endswith(".md") and "requirement" in low):
        return ("rule-source", "规则/记忆来源，待逐段分类")
    if low.endswith(".jsonl") and re.search(r"process|record|state|done|seen", low):
        return ("dedup-state", "去重/进度持久状态，保留")
    if low.endswith(".json"):
        if re.search(r"snapshot|last-|view|records|page|cache", low):
            return ("temp-state", "快照/中间状态 JSON，可再生")
        if at_root:
            return ("leaked-output", "泄漏到工作目录根层的数据 JSON")
    if at_root and low.endswith((".png", ".jpg", ".jpeg")) and re.search(r"qr|auth|tmp|temp|scratch", low):
        return ("misc-junk", "临时二维码/认证/草稿图")
    return None


def scan(workdir: Path):
    workdir = Path(workdir).resolve()
    entries = []
    env_dirs: list[Path] = []

    for root, dirs, files in os.walk(workdir, topdown=True):
        root = Path(root)
        # prune VCS + our own trash dir
        dirs[:] = [
            d for d in dirs
            if d not in PRUNE_ALWAYS and not d.startswith(".codex-cleanup-trash")
        ]
        for d in list(dirs):
            p = root / d
            if is_env_dir(p):
                env_dirs.append(p)
                dirs.remove(d)
            elif d == "node_modules":
                entries.append(make_entry(workdir, p, "env-node",
                                          reason="Node 依赖，可重装；体积大，建议手动确认"))
                dirs.remove(d)
            elif d == "__pycache__":
                entries.append(make_entry(workdir, p, "cache", reason="Python 字节码缓存，可再生"))
                dirs.remove(d)
            elif d == "tmp" or d == "temp":
                entries.append(make_entry(workdir, p, "temp-state", reason="临时/中间状态目录"))
                dirs.remove(d)
            elif d in ("runs", "assets", "drafts", "research", "processed"):
                entries.append(make_entry(workdir, p, "deliverable",
                                          reason="成品/资产/产出目录，保留"))
                dirs.remove(d)
        for f in files:
            p = root / f
            res = classify_file(workdir, p)
            if res:
                entries.append(make_entry(workdir, p, res[0], reason=res[1]))

    _group_environments(workdir, env_dirs, entries)
    entries.sort(key=lambda e: (-e["size"], e["category"]))

    return {
        "workdir": str(workdir),
        "generated": int(time.time()),
        "automations": find_automation_tomls(workdir),
        "conservative_quarantine": CONSERVATIVE_QUARANTINE,
        "entries": entries,
    }


def _group_environments(workdir: Path, env_dirs: list[Path], entries: list[dict]):
    if not env_dirs:
        return
    # Keep one: prefer the canonical name ".venv", then most recently modified.
    def sort_key(p: Path):
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = 0
        return (p.name == ".venv", mtime)

    chosen = max(env_dirs, key=sort_key)
    for p in env_dirs:
        if p == chosen:
            entries.append(make_entry(workdir, p, "env-keep", group="python-venv",
                                      reason="保留的 Python 环境（规范命名/最近修改）"))
        else:
            entries.append(make_entry(workdir, p, "redundant-env", group="python-venv",
                                      reason=f"冗余 Python 环境（已保留 {chosen.name}）"))


def render_markdown(inv: dict) -> str:
    lines = []
    wd = inv["workdir"]
    lines.append(f"# Codex automation 工件盘点\n")
    lines.append(f"- 工作目录：`{wd}`")
    autos = inv["automations"]
    if autos:
        for a in autos:
            lines.append(f"- 匹配正式配置：`{a['toml']}` (id=`{a['id']}` {a['name']})")
    else:
        lines.append("- 匹配正式配置：**未在 ~/.codex/automations 找到匹配 cwds**")
    lines.append("")

    by_cat: dict[str, list] = {}
    for e in inv["entries"]:
        by_cat.setdefault(e["category"], []).append(e)

    order = ["redundant-env", "env-keep", "env-node", "cache", "temp-state",
             "leaked-output", "misc-junk", "log", "rule-source", "dedup-state",
             "deliverable", "other"]
    label = {
        "redundant-env": "🧹 冗余环境（建议隔离，保留一套即可）",
        "env-keep": "✅ 保留的环境（一套）",
        "env-node": "📦 Node 依赖（手动确认）",
        "cache": "🧹 缓存（可再生）",
        "temp-state": "🧹 临时/快照状态（可再生）",
        "leaked-output": "🧹 根层泄漏数据 JSON",
        "misc-junk": "🧹 杂项垃圾",
        "log": "📜 日志（可归档）",
        "rule-source": "📋 规则/记忆来源（待逐段分类）",
        "dedup-state": "🔒 去重/进度状态（保留）",
        "deliverable": "🎁 成品/资产（保留）",
        "other": "❔ 其它",
    }
    total_q = 0
    for cat in order:
        items = by_cat.get(cat)
        if not items:
            continue
        cat_size = sum(i["size"] for i in items)
        if cat in CONSERVATIVE_QUARANTINE:
            total_q += cat_size
        lines.append(f"## {label.get(cat, cat)} — {len(items)} 项，{human_size(cat_size)}")
        for i in sorted(items, key=lambda x: -x["size"])[:25]:
            lines.append(f"- `{i['rel']}` — {human_size(i['size'])} — {i['reason']}")
        if len(items) > 25:
            lines.append(f"- …… 还有 {len(items) - 25} 项")
        lines.append("")

    lines.append(f"---\n**保守清理可隔离总量约 {human_size(total_q)}** "
                 f"（类别：{', '.join(CONSERVATIVE_QUARANTINE)}）。")
    lines.append("环境按类型分组：每组默认保留一套、其余标为 `redundant-env`。")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("workdir")
    ap.add_argument("--out", default="inventory.json", help="inventory JSON 输出路径")
    ap.add_argument("--toml", help="手动指定 automation.toml（跳过自动匹配）")
    args = ap.parse_args()

    wd = Path(args.workdir)
    if not wd.is_dir():
        sys.exit(f"工作目录不存在：{wd}")
    inv = scan(wd)
    if args.toml:
        inv["automations"] = [{"toml": args.toml, "id": "(manual)", "name": "", "cwd": str(wd)}]

    Path(args.out).write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    print(render_markdown(inv))
    print(f"\n[inventory 已写入 {args.out}]", file=sys.stderr)


if __name__ == "__main__":
    main()
