#!/usr/bin/env python3
"""Route classified markdown units into structured destination files.

Given units.json (from split_md.py) and a classification.json produced by the
model, this:
  - collects ``requirement`` units into requirements-extracted.md (deduped),
  - collects ``record`` units into run-history.md (chronological, deboilerplated),
  - backs up each touched source file into a trash dir and rewrites it to a
    short stub pointing at the new structure.

classification.json may be either a mapping ``{"u0007": "requirement"}`` or a
list of objects ``[{"id": "u0007", "label": "requirement", "text": "..."}]``.
An optional ``text`` overrides the unit text (useful when one unit mixes a rule
and a log line and you split it). Labels: requirement | record | drop.

Usage:
    route_md.py --units units.json --classification classification.json \
        [--requirements-out requirements-extracted.md] \
        [--history-out run-history.md] [--trash-dir DIR] [--apply]

Default is a dry run; pass --apply to write files and rewrite sources.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path


def load_classification(path: Path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = []  # list of (id, label, text_override|None)
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, dict):
                out.append((k, v.get("label", "unknown"), v.get("text")))
            else:
                out.append((k, v, None))
    elif isinstance(raw, list):
        for item in raw:
            out.append((item["id"], item.get("label", "unknown"), item.get("text")))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--units", required=True)
    ap.add_argument("--classification", required=True)
    ap.add_argument("--requirements-out", default="requirements-extracted.md")
    ap.add_argument("--history-out", default="run-history.md")
    ap.add_argument("--trash-dir", default=None)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    units = {u["id"]: u for u in json.loads(Path(args.units).read_text(encoding="utf-8"))}
    classification = load_classification(Path(args.classification))

    ts = time.strftime("%Y%m%d-%H%M%S")
    trash = Path(args.trash_dir) if args.trash_dir else Path(".codex-cleanup-trash") / ts / "_rule-sources"

    req_blocks = []   # (source_file, text)
    rec_blocks = []   # (source_file, heading, text)
    seen_req = set()
    touched_sources = set()
    counts = {"requirement": 0, "record": 0, "drop": 0, "unknown": 0}

    for uid, label, override in classification:
        u = units.get(uid)
        if u is None:
            print(f"警告：classification 引用了未知单元 {uid}", file=sys.stderr)
            continue
        text = (override if override is not None else u["text"]).strip()
        touched_sources.add(u["source_file"])
        counts[label] = counts.get(label, 0) + 1
        if label == "requirement":
            key = text
            if key in seen_req:
                continue
            seen_req.add(key)
            req_blocks.append((u["source_file"], text))
        elif label == "record":
            rec_blocks.append((u["source_file"], u.get("heading"), text))

    # Build destination contents -----------------------------------------
    req_md = _build_requirements(req_blocks, ts)
    hist_md = _build_history(rec_blocks, ts)

    print("=== 分流计划 ===")
    print(f"requirement: {counts.get('requirement', 0)}（去重后 {len(req_blocks)}） "
          f"record: {counts.get('record', 0)} drop: {counts.get('drop', 0)} "
          f"unknown: {counts.get('unknown', 0)}")
    print(f"→ 需求清单: {args.requirements_out}")
    print(f"→ 运行历史: {args.history_out}")
    print("→ 待重写为指针并备份的源文件:")
    for s in sorted(touched_sources):
        print(f"    {s}   (备份到 {trash}/)")

    if not args.apply:
        print("\n[dry-run] 加 --apply 才会写文件并重写源文件。")
        return

    Path(args.requirements_out).write_text(req_md, encoding="utf-8")
    Path(args.history_out).write_text(hist_md, encoding="utf-8")
    trash.mkdir(parents=True, exist_ok=True)
    for s in sorted(touched_sources):
        sp = Path(s)
        if not sp.exists():
            continue
        shutil.copy2(sp, trash / sp.name)
        sp.write_text(_stub(sp.name, args.requirements_out, args.history_out, trash, ts), encoding="utf-8")
    print(f"\n已写出 {args.requirements_out}、{args.history_out}；源文件已备份至 {trash} 并重写为指针。")


def _build_requirements(blocks, ts):
    out = [f"# 已提取的用户要求（{ts}）\n",
           "> 由 codex-automation-cleanup 从 memory.md / *REQUIREMENTS*.md 逐段提取、去重。",
           "> 审核后由 restructure_toml.py 合并进 automation.toml 的 prompt。\n"]
    by_src = {}
    for src, text in blocks:
        by_src.setdefault(src, []).append(text)
    for src, texts in by_src.items():
        out.append(f"## 来源：`{src}`\n")
        for t in texts:
            out.append(t if t.lstrip().startswith(("-", "*", "#")) else f"- {t}")
        out.append("")
    if not blocks:
        out.append("_（无）_")
    return "\n".join(out) + "\n"


def _build_history(blocks, ts):
    out = [f"# 运行历史归档（{ts}）\n",
           "> 由 codex-automation-cleanup 从 memory.md 抽出的运行/过程记录。仅供追溯，"
           "不再作为下一轮 Agent 的指令来源。\n"]
    cur = None
    for src, heading, text in blocks:
        if heading and heading != cur:
            out.append(f"\n## {heading}")
            cur = heading
        out.append(text if text.lstrip().startswith(("-", "*")) else f"- {text}")
    if not blocks:
        out.append("_（无）_")
    return "\n".join(out) + "\n"


def _stub(name, req_out, hist_out, trash, ts):
    return (
        f"# {name}（已整理 {ts}）\n\n"
        f"本文件已被 codex-automation-cleanup 整理，以重建 single source of truth：\n\n"
        f"- **用户要求** 已提取到 `{req_out}`，并合并进 automation.toml 的 `prompt`。\n"
        f"- **运行/过程记录** 已归档到 `{hist_out}`。\n"
        f"- 原始内容备份：`{trash}/{name}`。\n\n"
        f"> 请不要再把长期要求写到本文件；要求应进 automation.toml，运行记录应进 {hist_out}。\n"
    )


if __name__ == "__main__":
    main()
