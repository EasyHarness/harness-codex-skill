# harness-codex-skill

**简体中文** | [English](./README.en.md)

收拾 **Codex automation（自动化任务）** 在工作目录里留下的烂摊子的 Agent Skill。

---

## 你是不是也这样

> 我给自动化任务提了条要求——比如「每段别太长」「字数要够」——让它记住。可它下一轮照样犯同样的错，像个没记性的员工，踢一下动一下。
>
> 想搞清楚我到底给它提过哪些要求，得翻三个文件：`memory.md`、`AUTOMATION_REQUIREMENTS.md`，还有 `automation.toml`。同一条要求我甚至重复写了两遍都没发现。`memory.md` 里要求和运行日志还混在一起，越堆越长。
>
> 跑了一周，工作目录里冒出四套 Python 环境、一堆 tmp 快照、泄漏到根目录的中间 json，没人清理。一个任务才跑一周，就有种彻底失控的感觉——我要的只是：**所有要求有一个唯一真源，跑完别留一地鸡毛。**

这正是本 Skill 要解决的。它的核心**不是删文件**，而是重建 single source of truth：

1. 逐段判读 `memory.md` / `*REQUIREMENTS*.md`，把**用户要求**与**运行记录**分流到不同文件；
2. 把散落的长期要求合并进 `~/.codex/automations/<id>/automation.toml` 的 `prompt`，并把这坨无结构长字符串**重写成清晰分节**；
3. 通用地清理冗余 Python/Node 环境、缓存、tmp 快照、泄漏到根目录的数据文件等可丢弃产物——**隔离到可恢复的回收目录，绝不硬删除**。

所有逻辑都是通用的，不针对任何具体项目写死规则。

---

## 环境要求

- **任意 `python3`**（≥3.8 即可；脚本**零第三方依赖**）。
- 若有 `python3.11+`（自带 `tomllib`）或装了 `tomli`，TOML 校验会更严格；没有也能跑（内置精简解析器兜底）。
- 仅在本机文件系统上工作；不联网。

---

## 安装

这是一个标准的 **Agent Skill**：一个含 `SKILL.md` 的目录。安装 = 把这个目录（或其符号链接）放进 Agent 的 skills 目录，**目录名用 `harness-codex-skill`**。

### 一句话安装（推荐）

现在的 Agent 大多能自己装 skill。直接把下面这段**粘进 Claude Code / Codex 等的聊天框**，它会识别自己是什么 Agent 并放到正确位置：

```
把 https://github.com/EasyHarness/harness-codex-skill 这个 skill 装到你的 skills 目录：
clone 下来（或拉取最新），按你的运行环境放到对应位置（如 Claude Code 用 ~/.claude/skills，
Codex 用 ~/.codex/skills），目录名用 harness-codex-skill，可以用软链接。装完确认 SKILL.md 在位。
```

装好后重开（或刷新）一下会话即可。若想手动安装、或你的 Agent 不能自助安装，见下面的分步说明。

### 手动安装

先把仓库拉到本地任意位置：

```bash
git clone https://github.com/orange90/harness-codex-skill ~/src/harness-codex-skill
# 或者你已经有了这个目录，记下它的绝对路径，下文用 $SKILL_SRC 表示
SKILL_SRC=~/src/harness-codex-skill
```

#### Claude Code

用户级（对所有项目可用）：

```bash
mkdir -p ~/.claude/skills
ln -s "$SKILL_SRC" ~/.claude/skills/harness-codex-skill
# 不想用软链就直接拷贝： cp -R "$SKILL_SRC" ~/.claude/skills/harness-codex-skill
```

项目级（只在某个仓库内可用）：

```bash
mkdir -p <your-project>/.claude/skills
ln -s "$SKILL_SRC" <your-project>/.claude/skills/harness-codex-skill
```

重开（或刷新）Claude Code 后，`SKILL.md` 的 `description` 命中时会自动加载；也可直接说「用 harness-codex-skill 收拾一下这个目录」。

#### Codex

```bash
mkdir -p ~/.codex/skills
ln -s "$SKILL_SRC" ~/.codex/skills/harness-codex-skill
# 或 cp -R "$SKILL_SRC" ~/.codex/skills/harness-codex-skill
```

Codex 的 skills 与 Claude Code 同构（目录 + `SKILL.md`）。放好后在会话里让它整理对应工作目录即可。

> 小贴士：本 Skill 正是用来清理 Codex automation 的产物，把它装在 Codex 上能形成「自己收拾自己」的闭环。

#### OpenClaw / Hermes / 其他支持 SKILL.md 的 Agent

凡是遵循开放 **Agent Skill（`SKILL.md` + YAML frontmatter）** 约定的 Agent，安装方式都一样——把目录放进该 Agent 的技能目录，常见位置：

```
<agent 配置根>/skills/harness-codex-skill/
```

把 `<agent 配置根>` 换成该 Agent 的配置目录（如 `~/.openclaw`、`~/.hermes` 之类，以各自文档为准），其余同上。不确定路径时，查该 Agent「skills / plugins / extensions」相关文档，找它扫描技能的目录。

### 不支持 Skill 机制的 Agent（手动模式）

把 `SKILL.md` 的内容作为系统提示 / 上下文喂给 Agent，让它按其中的 7 步工作流调用 `scripts/` 下的脚本即可。脚本本身是自洽的命令行工具（见下文「独立使用」），不依赖任何 Agent 运行时。

---

## 触发方式

装好后，下面这类话都会命中本 Skill：

- 「Codex 自动化任务的工作目录太乱了，帮我收拾一下 `~/Documents/xxx`」
- 「把 `memory.md` 里的要求合并进 automation.toml」
- 「automation.toml 没结构，重新整理一下」
- 「跑出一堆 venv / tmp / 中间 json 没清理」

Agent 会依次：定位工作目录与 `automation.toml` → 盘点报告 → 逐段分类 → 重建并结构化 `prompt` → 分流记录、瘦身 `memory.md` → 隔离清理产物 → 汇总。每个会改动磁盘的步骤都**先 dry-run、再确认**。

---

## 安全保证

- **隔离而非删除**：清理一律 move 到 `<workdir>/.codex-cleanup-trash/<时间戳>/`，附 `manifest.json` 与 `RESTORE.sh`，可一键还原；彻底删除由你确认后手动 `rm -rf`。
- **改前先备份**：改 `automation.toml` 会写 `*.bak.<时间戳>`，并做**写回后解析校验**与 diff 展示。
- **保护成品与状态**：`runs/`、`assets/`、去重状态 `*.jsonl` 等默认绝不动。
- **多套环境保留一套**：检测到重复运行环境时保留一个、隔离其余，不删光。

---

## 目录结构

```
harness-codex-skill/
├── SKILL.md                      # Agent 入口：触发条件 + 工作流 + 安全总则
├── README.md                     # 本文档（中文）
├── README.en.md                  # English documentation
├── scripts/                      # 零依赖命令行工具
│   ├── scan.py                   # 盘点+分类工件（含环境分组去重）
│   ├── split_md.py               # 把 memory/REQUIREMENTS 切成原子段落单元
│   ├── route_md.py               # 按分类把段落分流到不同文件、备份并重写源文件
│   ├── restructure_toml.py       # 备份并安全替换 automation.toml 的 prompt 字段
│   ├── cleanup.py                # 按类别隔离产物到可恢复回收目录
│   └── _common.py                # 共享：TOML 读取 + 配置匹配 + 体积统计
└── references/                   # Agent 按需加载的判据与模板
    ├── classification-guide.md   # 用户要求 vs 运行记录的通用判据
    ├── toml-structure.md         # 结构化 prompt 骨架模板
    └── artifact-taxonomy.md      # 工件分类表与检测特征
```

---

## 独立使用（不经 Agent）

脚本也可单独当命令行工具跑，先看再动手：

```bash
# 1) 盘点（只读，写出 inventory.json + 打印报告）
python3 scripts/scan.py <工作目录> --out /tmp/inventory.json

# 2) 切分规则/记忆文件，供人工或模型分类
python3 scripts/split_md.py <…>/memory.md <…>/AUTOMATION_REQUIREMENTS.md --out /tmp/units.json

# 3) 按 classification.json 分流（默认 dry-run，加 --apply 才落盘）
python3 scripts/route_md.py --units /tmp/units.json --classification /tmp/classification.json --apply

# 4) 把整理好的新 prompt 写回 toml（默认 dry-run 看 diff，--apply 才写、自动备份）
python3 scripts/restructure_toml.py --toml <automation.toml> --prompt-file /tmp/new_prompt.txt --apply

# 5) 隔离清理（默认 dry-run，--apply 才移动；可恢复）
python3 scripts/cleanup.py --inventory /tmp/inventory.json --apply
```

各脚本加 `-h` 看完整参数。`classification.json` 的格式见 `references/classification-guide.md`。

---

## License

MIT
