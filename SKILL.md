---
name: harness-codex-skill
description: >-
  整理并结构化 Codex automation（自动化任务）在工作目录里留下的烂摊子。逐段判读 memory.md /
  AUTOMATION_REQUIREMENTS.md，把「用户要求」与「运行记录」分流到不同文件，将散落的长期要求合并进
  ~/.codex/automations/<id>/automation.toml 的 prompt 并重新结构化，重建 single source of
  truth；同时通用地清理冗余 Python/Node 环境、缓存、tmp 快照、泄漏到根目录的数据 JSON 等可丢弃产物
  （隔离到可恢复的回收目录，绝不硬删除）。当用户提到 Codex 自动化任务的工作目录混乱、屎山、收拾/整理
  automation 产物、memory.md 太乱、把要求合并进 automation.toml、automation.toml 缺结构、
  跑出一堆 venv/tmp/中间文件没清理时，**务必使用本技能**，即使用户没说出「skill」二字。
license: MIT
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
---

# harness-codex-skill

收拾 Codex automation 工作目录的屎山。核心**不是删文件**，而是重建 single source of truth：

1. 逐段判断 `memory.md` / `*REQUIREMENTS*.md` 的内容是**用户要求**还是**运行记录**，分流到不同文件；
2. 把长期要求合并进 `automation.toml` 的 `prompt`，并把这坨无结构长字符串**重写成清晰分节**；
3. 顺手**通用地**清理可丢弃产物（冗余环境/缓存/tmp/根层泄漏数据），隔离到可恢复的回收目录。

所有判断与脚本都是通用的——不针对任何具体项目写死规则。脚本用任意 `python3` 都能跑（无第三方依赖）。

## 安全总则（始终遵守）

- **隔离而非删除**：清理一律 move 到 `<workdir>/.codex-cleanup-trash/<ts>/`，附 manifest 与 `RESTORE.sh`，可还原。彻底删除只由用户确认后手动执行。
- **先 dry-run**：每个会改动磁盘的脚本默认 dry-run，看清计划/diff 后再 `--apply`。
- **改前先备份**：改 `automation.toml` 或重写源 `.md` 一定先备份并展示 diff/计划给用户确认。
- **保护成品与状态**：`deliverable / dedup-state` 默认绝不动；删了去重状态会导致重复跑。
- **合并前去重**：把要求并进 prompt 前，先对照现有 prompt，已存在的不重复加入。
- **环境保留一套**：多套同类环境保留一套、隔离其余，不删光。

脚本位置：`scripts/`；判据与模板：`references/`。下面的 `$SKILL` 指本技能目录。

## 工作流

### 1. 定位
确认要整理的工作目录（用户给的，或就是当前 cwd）。运行盘点：

```bash
python3 "$SKILL/scripts/scan.py" "<workdir>" --out /tmp/inventory.json
```

它会自动在 `~/.codex/automations/*/automation.toml` 里按 `cwds` 匹配出正式配置。多个 automation 命中就逐个处理。若没匹配到，问用户对应哪个 automation。

### 2. 盘点报告
把 `scan.py` 的 Markdown 输出读给用户，点明三大现状：要求散落多处、环境/产物堆积、`prompt` 无结构。让用户对整体有数。

### 3. 逐段分类（核心）
切分规则/记忆文件：

```bash
python3 "$SKILL/scripts/split_md.py" "<workdir>/.../memory.md" "<workdir>/.../AUTOMATION_REQUIREMENTS.md" --out /tmp/units.json
```

读 `references/classification-guide.md`，**逐个 unit 判定** `requirement` / `record` / `drop`（脚本的 `guess` 仅供参考）。遇到一段里既有规则又有记录就**拆开**（同 id 出两条，requirement 用 `text` 给提炼后的纯规则）。对照现有 prompt 把重复要求标 `drop`。把结果写成 `/tmp/classification.json`。

### 4. 重建并结构化 automation.toml
先读现有 `prompt` 与 `requirements-extracted.md`，按 `references/toml-structure.md` 的骨架，把「现有 prompt + 审核通过的新增要求」**重写成分节、去重的完整 prompt**，写到 `/tmp/new_prompt.txt`。然后：

```bash
python3 "$SKILL/scripts/restructure_toml.py" --toml "<automation.toml>" --prompt-file /tmp/new_prompt.txt           # dry-run，看 diff
python3 "$SKILL/scripts/restructure_toml.py" --toml "<automation.toml>" --prompt-file /tmp/new_prompt.txt --apply   # 用户确认后
```

脚本会备份、做写回后解析校验、默认以可读的多行字符串写入。**把 diff 给用户确认后再 `--apply`。**

### 5. 分流记录、瘦身 memory
```bash
python3 "$SKILL/scripts/route_md.py" --units /tmp/units.json --classification /tmp/classification.json \
  --requirements-out "<workdir>/requirements-extracted.md" --history-out "<workdir>/run-history.md"            # dry-run
# 用户确认后加 --apply：record 归档到 run-history.md，源 md 备份后重写为指针
```

提醒用户：以后长期要求进 `automation.toml`，运行记录进 `run-history.md`，别再回头堆 `memory.md`。

### 6. 清理产物
```bash
python3 "$SKILL/scripts/cleanup.py" --inventory /tmp/inventory.json                # dry-run，保守默认集
```

用 `AskUserQuestion` 让用户增减类别（如是否把 `log`、一次性补丁脚本也归档进来——「激进」选项）。确认后：

```bash
python3 "$SKILL/scripts/cleanup.py" --inventory /tmp/inventory.json --apply
# 自定义类别：--categories redundant-env,cache,temp-state,leaked-output,misc-junk,log
```

### 7. 收尾汇总
告诉用户：
- 新的 single source of truth = `automation.toml` 的结构化 prompt（备份在 `*.bak.<ts>`）；
- 文件归类结果（要求 / 历史 / 保留项）；
- 隔离了哪些、释放多少空间、回收目录路径；
- 如何 `bash RESTORE.sh` 还原，或确认后 `rm -rf` 回收目录彻底删除。

## 备注
- `scan.py` 把 `runs/assets/drafts/research/processed` 当作品/资产保留，把 `*.jsonl` 去重状态保留——不要在没明确同意时把它们加进清理类别。
- 一次性补丁脚本（`tools/*.py` 之类）默认归在 `other`（保留）。若用户想清掉，归档而非删除，并先确认它们确实没被 `automation.toml` 的流程引用。
