# harness-codex-skill

[简体中文](./README.md) | **English**

An Agent Skill that cleans up the mess left behind by **Codex automation (automated tasks)** in your working directory.

---

## Sound familiar?

> I told the automated task to remember a rule — say, "keep paragraphs short" or "hit the word count." Yet the next run it makes the exact same mistake, like an employee with no memory: it only moves when you kick it.
>
> To figure out what I'd even asked of it, I had to dig through three files: `memory.md`, `AUTOMATION_REQUIREMENTS.md`, and `automation.toml`. I'd written the same rule twice without noticing. And `memory.md` mixes the rules in with the run logs, growing longer by the day.
>
> After a week, the working directory had sprouted four separate Python environments, a pile of tmp snapshots, and intermediate json files leaked into the project root — nothing cleaned up. One week in and the whole thing already felt out of control. All I wanted was: **one single source of truth for every requirement, and no debris left behind after each run.**

That's exactly what this Skill is for. Its core purpose is **not deleting files**, but rebuilding a single source of truth:

1. Reads `memory.md` / `*REQUIREMENTS*.md` paragraph by paragraph and splits **user requirements** from **run records** into different files;
2. Merges scattered long-term requirements into the `prompt` field of `~/.codex/automations/<id>/automation.toml`, and **rewrites that unstructured blob into clearly separated sections**;
3. Generically cleans up redundant Python/Node environments, caches, tmp snapshots, data files leaked to the project root, and other disposable artifacts — **isolated into a recoverable trash directory, never hard-deleted**.

All logic is generic and never hard-codes rules for any specific project.

---

## Requirements

- **Any `python3`** (≥3.8 is fine; the scripts have **zero third-party dependencies**).
- With `python3.11+` (which ships with `tomllib`) or `tomli` installed, TOML validation is stricter; without them it still works (a built-in minimal parser is used as a fallback).
- Operates only on the local filesystem; no network access.

---

## Installation

This is a standard **Agent Skill**: a directory containing `SKILL.md`. Installing = put this directory (or a symlink to it) into the Agent's skills directory, **using the name `harness-codex-skill`**.

### One-shot install (recommended)

Most modern Agents can install skills themselves. Just **paste the following into your Claude Code / Codex chat box**; the Agent will figure out which runtime it is and place the skill correctly:

```
Install the skill at https://github.com/EasyHarness/harness-codex-skill into your skills directory:
clone it (or pull the latest), and place it where appropriate for your runtime (e.g. ~/.claude/skills for
Claude Code, ~/.codex/skills for Codex), using the directory name harness-codex-skill. A symlink is fine.
After install, confirm SKILL.md is in place.
```

After installation, restart (or refresh) the session. If you prefer manual install, or your Agent cannot self-install, see the step-by-step instructions below.

### Manual install

First clone the repo to any local location:

```bash
git clone https://github.com/orange90/harness-codex-skill ~/src/harness-codex-skill
# Or if you already have this directory, note its absolute path; below it is referred to as $SKILL_SRC
SKILL_SRC=~/src/harness-codex-skill
```

#### Claude Code

User-level (available to all projects):

```bash
mkdir -p ~/.claude/skills
ln -s "$SKILL_SRC" ~/.claude/skills/harness-codex-skill
# If you don't want a symlink, copy directly: cp -R "$SKILL_SRC" ~/.claude/skills/harness-codex-skill
```

Project-level (only available inside a particular repo):

```bash
mkdir -p <your-project>/.claude/skills
ln -s "$SKILL_SRC" <your-project>/.claude/skills/harness-codex-skill
```

After restarting (or refreshing) Claude Code, the skill will auto-load when `SKILL.md`'s `description` matches; you can also just say "use harness-codex-skill to tidy up this directory".

#### Codex

```bash
mkdir -p ~/.codex/skills
ln -s "$SKILL_SRC" ~/.codex/skills/harness-codex-skill
# or cp -R "$SKILL_SRC" ~/.codex/skills/harness-codex-skill
```

Codex skills follow the same structure as Claude Code (directory + `SKILL.md`). Once installed, just ask it to tidy up the corresponding working directory in a session.

> Tip: This Skill is precisely designed to clean up Codex automation artifacts. Installing it on Codex creates a "clean up after yourself" loop.

#### OpenClaw / Hermes / Other Agents that support SKILL.md

Any Agent that follows the open **Agent Skill (`SKILL.md` + YAML frontmatter)** convention installs the same way — drop the directory into the Agent's skills directory, typically:

```
<agent config root>/skills/harness-codex-skill/
```

Replace `<agent config root>` with that Agent's config directory (e.g. `~/.openclaw`, `~/.hermes`, etc., per their own docs); everything else is the same. If you're unsure of the path, check the Agent's "skills / plugins / extensions" docs for the directory it scans for skills.

### Agents without a Skill mechanism (manual mode)

Feed the contents of `SKILL.md` to the Agent as a system prompt / context, and have it follow the 7-step workflow inside to invoke the scripts under `scripts/`. The scripts are self-contained CLI tools (see "Standalone usage" below) and depend on no Agent runtime.

---

## Triggering

Once installed, phrases like these will hit this Skill:

- "The Codex automation working directory is a mess, please tidy up `~/Documents/xxx`"
- "Merge the requirements in `memory.md` into automation.toml"
- "automation.toml has no structure, restructure it"
- "A bunch of venv / tmp / intermediate json files haven't been cleaned up"

The Agent will, in order: locate the working directory and `automation.toml` → produce an inventory report → classify paragraph by paragraph → rebuild and structure the `prompt` → split records and slim down `memory.md` → isolate cleanup artifacts → summarize. Every step that touches disk **dry-runs first, then asks for confirmation**.

---

## Safety guarantees

- **Isolation, not deletion**: cleanup always moves things to `<workdir>/.codex-cleanup-trash/<timestamp>/`, with a `manifest.json` and a `RESTORE.sh`, so you can one-click restore; permanent deletion is left to you via a manual `rm -rf`.
- **Backup before edit**: editing `automation.toml` writes a `*.bak.<timestamp>`, and performs a **parse-check after writing** along with a diff display.
- **Protects products and state**: `runs/`, `assets/`, deduplication state `*.jsonl`, etc. are never touched by default.
- **Keep one of duplicated environments**: when duplicate runtime environments are detected, one is kept and the rest are isolated — never wiped clean.

---

## Directory structure

```
harness-codex-skill/
├── SKILL.md                      # Agent entry: trigger conditions + workflow + safety principles
├── README.md                     # Chinese documentation
├── README.en.md                  # This document
├── scripts/                      # Zero-dependency CLI tools
│   ├── scan.py                   # Inventory + classify artifacts (incl. env grouping & dedup)
│   ├── split_md.py               # Splits memory/REQUIREMENTS into atomic paragraph units
│   ├── route_md.py               # Routes paragraphs to different files by classification, backs up and rewrites the source
│   ├── restructure_toml.py       # Backs up and safely replaces the prompt field of automation.toml
│   ├── cleanup.py                # Isolates artifacts into a recoverable trash directory by category
│   └── _common.py                # Shared: TOML reading + config matching + size accounting
└── references/                   # Criteria & templates the Agent loads on demand
    ├── classification-guide.md   # Generic criteria for user requirements vs run records
    ├── toml-structure.md         # Skeleton template for a structured prompt
    └── artifact-taxonomy.md      # Artifact taxonomy table & detection features
```

---

## Standalone usage (without an Agent)

The scripts can also be run as standalone CLI tools — inspect first, then act:

```bash
# 1) Inventory (read-only, writes inventory.json + prints a report)
python3 scripts/scan.py <workdir> --out /tmp/inventory.json

# 2) Split rule/memory files for manual or model-based classification
python3 scripts/split_md.py <…>/memory.md <…>/AUTOMATION_REQUIREMENTS.md --out /tmp/units.json

# 3) Route by classification.json (dry-run by default; add --apply to actually write)
python3 scripts/route_md.py --units /tmp/units.json --classification /tmp/classification.json --apply

# 4) Write the cleaned-up new prompt back into toml (dry-run by default to view diff; --apply to actually write, auto-backup)
python3 scripts/restructure_toml.py --toml <automation.toml> --prompt-file /tmp/new_prompt.txt --apply

# 5) Isolate cleanup artifacts (dry-run by default; --apply to actually move; recoverable)
python3 scripts/cleanup.py --inventory /tmp/inventory.json --apply
```

Run each script with `-h` for the full parameter list. The format of `classification.json` is described in `references/classification-guide.md`.

---

## License

MIT
