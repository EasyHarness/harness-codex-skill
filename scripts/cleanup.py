#!/usr/bin/env python3
"""Quarantine selected artifacts into a recoverable trash dir.

Reads inventory.json (from scan.py) and moves entries whose category is in the
selected set into ``<workdir>/.codex-cleanup-trash/<ts>/`` (preserving relative
layout), alongside a manifest.json and a RESTORE.sh. Nothing is hard-deleted.

Protected by default: deliverable, dedup-state, rule-source, log, env-keep,
env-node — they are only moved if you explicitly name their category.

Usage:
    cleanup.py --inventory inventory.json [--categories a,b,c] [--apply]

Default categories are the conservative set from the inventory. Default is a
dry run; pass --apply to actually move files.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import human_size  # noqa: E402

NEVER_AUTO = {"deliverable", "dedup-state", "rule-source", "env-keep"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--categories", help="逗号分隔；默认用 inventory 的保守集")
    ap.add_argument("--trash-dir", default=None)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    inv = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    workdir = Path(inv["workdir"])
    if args.categories:
        cats = [c.strip() for c in args.categories.split(",") if c.strip()]
    else:
        cats = inv.get("conservative_quarantine", [])

    risky = [c for c in cats if c in NEVER_AUTO]
    if risky:
        print(f"⚠️  你选择了受保护类别 {risky}，将一并隔离（成品/状态/规则源会被移走）。",
              file=sys.stderr)

    selected = [e for e in inv["entries"] if e["category"] in cats]
    if not selected:
        print("没有匹配所选类别的条目。")
        return

    ts = time.strftime("%Y%m%d-%H%M%S")
    trash = Path(args.trash_dir) if args.trash_dir else workdir / ".codex-cleanup-trash" / ts

    total = sum(e["size"] for e in selected)
    print(f"=== 清理计划（{'APPLY' if args.apply else 'DRY-RUN'}）===")
    print(f"类别：{', '.join(cats)}")
    print(f"条目：{len(selected)} 项，约 {human_size(total)} → 隔离到 {trash}\n")
    for e in sorted(selected, key=lambda x: -x["size"]):
        print(f"  [{e['category']}] {e['rel']}  ({human_size(e['size'])})  {e['reason']}")

    if not args.apply:
        print(f"\n[dry-run] 加 --apply 才会移动文件。可恢复，不会硬删除。")
        return

    trash.mkdir(parents=True, exist_ok=True)
    manifest = []
    restore_lines = ["#!/bin/bash", "# 由 codex-automation-cleanup 生成；运行本脚本可把隔离文件还原。", "set -e", ""]
    for e in selected:
        src = Path(e["path"])
        if not src.exists():
            continue
        rel = e["rel"]
        dest = trash / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        manifest.append({
            "original": str(src), "moved_to": str(dest),
            "rel": rel, "category": e["category"], "size": e["size"], "reason": e["reason"],
        })
        restore_lines.append(f'mkdir -p {sh_quote(str(src.parent))}')
        restore_lines.append(f'mv {sh_quote(str(dest))} {sh_quote(str(src))}')

    (trash / "manifest.json").write_text(
        json.dumps({"workdir": str(workdir), "ts": ts, "items": manifest},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    restore = trash / "RESTORE.sh"
    restore.write_text("\n".join(restore_lines) + "\n", encoding="utf-8")
    restore.chmod(0o755)
    print(f"\n已隔离 {len(manifest)} 项到 {trash}。")
    print(f"恢复：bash {restore}")
    print(f"确认无误后彻底删除：rm -rf {trash}")


def sh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


if __name__ == "__main__":
    main()
