# 工件分类表（通用）

`scan.py` 按**结构特征**而非项目词分类。下表是判定规则与默认动作；运行时可按需调整选中的类别。

| 类别 | 检测特征（通用） | 默认动作 | 理由 |
|---|---|---|---|
| `env-keep` | 含 `pyvenv.cfg` 或 `bin/activate` 的目录中，每个类型组保留一个（优先 `.venv`，否则最近修改） | 保留 | 运行需要一套环境 |
| `redundant-env` | 同类型环境里非保留的其余几套 | 隔离 | 重复堆积的虚拟环境，可重建 |
| `env-node` | `node_modules/` | 保留（手动确认） | 可重装，但可能分属不同子项目，默认不动 |
| `cache` | `__pycache__/`、`*.pyc`/`*.pyo` | 隔离 | 编译缓存，可再生 |
| `temp-state` | `tmp/`、`temp/`，及 `*snapshot*` / `last-*` / `*records*` / `view.json` / `*page*` 等中间 JSON | 隔离 | 单次运行的快照/中间态，可再生 |
| `leaked-output` | 工作目录**根层**散落的数据 JSON（非已知配置/状态文件） | 隔离 | 本应落在子目录、泄漏到根目录的中间数据 |
| `misc-junk` | `.DS_Store`、`Thumbs.db`，根层 `*qr*`/`*auth*`/`*tmp*` 图片 | 隔离 | 系统元数据/临时图 |
| `log` | `*run-log*.md`、`*run-report*.md` | 保留 | 运行日志，可后续手动归档 |
| `rule-source` | `memory.md`、`*REQUIREMENTS*.md` | 保留 | 规则/记忆来源，交给 split_md/route_md 处理 |
| `dedup-state` | `*.jsonl` 且名含 process/record/state/done/seen | 保留 | 去重/进度状态，删了会重复跑 |
| `deliverable` | `runs/`、`assets/`、`drafts/`、`research/`、`processed/` 目录 | 保留 | 成品与资产 |
| `other` | 未匹配 | 保留 | 不确定就不动 |

## 环境去重逻辑

`scan.py` 把所有 venv 目录归为一个组，按「`.venv` 优先、其次最近修改时间」选一个保留（`env-keep`），其余记为 `redundant-env`。这就实现了「有几套环境就保留一套、清掉冗余」，而不是把环境删光。Node `node_modules` 因可能分属不同子项目，默认仅报告不隔离。

## 保守清理默认集

`cleanup.py` 默认隔离：`redundant-env, cache, temp-state, leaked-output, misc-junk`。
`deliverable / dedup-state / rule-source / env-keep` 受保护，只有显式 `--categories` 指名才会被移动。
`log / env-node` 不在默认集，需要时手动加入（如「激进：归档历史」时把 `log` 加进来）。

## 安全网

- 全部默认 `--dry-run`，`--apply` 才动手。
- 隔离=移动到 `<workdir>/.codex-cleanup-trash/<ts>/`，附 `manifest.json` 与 `RESTORE.sh`，可一键还原；从不硬删除。
- 彻底删除由用户在确认后手动 `rm -rf` 回收目录。
