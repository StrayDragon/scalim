# Design: YAML vs Python policy boundary（c40）

## 范围

本 change：**盘点 + 原则 + follow-up 列表**。不改 `src/scalim` schema，不 `change start` 除非升格 Full。

交付物：

- `inventory.md`（R1，含统一术语）
- 本节 R2 原则
- 下方 R3：文档对齐走 **quick**（不另开 change）

## 与 c30 / 0.10 的关系

- c30 **保留** `sources.*.lookup_chunk_size`（keys 分片大小）。
- c30 **不**新增 YAML 并行键；并行 = Python opt-in（0.10.0：`parallelize_lookup_chunks`）。
- 本调研 **确认** 该键中长期仍属 YAML「需求侧上限提示」，**不**开迁出 follow-up。
- 0.10.* 主线叙事：YAML **无强制迁移**；边界收口靠文档/skill 统一理解，不靠再删键。

## R2 边界原则（文档级；合约仍以 live specs 为准）

术语见 `inventory.md`「术语」表。

1. **MUST 留 YAML**：数据流图与资源身份——`runs`/deps、`main_source`/`sources` 身份与 loader 引用、`fields`/`relations`、`resources.*.id+path`、`outputs.to`/`fields`/`where`/`aggregate`、内容字段与 `params` 指令节点（含 `$rows.cache_mode`）。
2. **MUST 仅 Python（已落地）**：并发与 worker、loader retry、guardrails、demand/workflow failure diagnostics（含 `validate_unique_field_names`）、book **write strategy**（`BookWritePolicy`）、workflow `cache_pool` / `resources_wait`、observers/viz、security allowlist、`init_vars`、ExcelColumnResidency。
3. **SHOULD 仅 Python**：与宿主/环境强相关、写入后难复现的调优（batch_size、max_workers、parallelize_*）。已迁出的不得回流 YAML。
4. **灰区（YAML 可选提示 + Python 覆盖/扩展）**：`lookup_chunk_size`；`sources.*.cache_mode` 粗枚举；`allow_formulas` / 静态 `encoding`；`outputs.*.write` 仅 header 局部。Python 不得靠「静默忽略 YAML」改语义而不文档化。
5. **禁止**：未完成 inventory 就删 YAML 键；把编排/内容键误迁 Python；复活 budget / Dedup / TwoStage / `write_defaults`；把 `sources.*.cache_mode` 与 `$rows.cache_mode` 混称；把 `lookup_chunk_size` 当成并行开关。
6. **第一刀默认**：文档 + agent/skill 对齐（见 R3 quick 清单）；不做 breaking deprecation，除非独立 propose 带兼容窗。

对照：`AGENTS.md` Hard Rules、capability-matrix、live `yaml-dsl-runtime-policy-boundary`、c30 例外、0.10 release highlights。

## R3 文档对齐（`llman-sdd-quick`，无独立 change）

不改 MUST/SHALL、不迁键、不改 schema → **quick path**。本 inventory 为调研 SSOT；入口页只做速记 + 链接，避免双写。

| # | 落点 | 改什么 |
|---|------|--------|
| Q1 | `docs/doc/yaml-dsl/review-checklist.md` | Authoring 边界速记补灰区 + 链本 `inventory.md` |
| Q2 | `docs/doc/yaml-dsl/index.md` | 主线原则下「边界速查」链 |
| Q3 | `docs/doc/yaml-dsl/capability-matrix.md` | `lookup_chunk_size` / `cache_mode` 行补灰区短注 |
| Q4 | `agentdev/skills/scalim-yaml-dsl/references/yaml-runtime-policy-boundary.md`（新） | 三栏判定 + 两套 cache_mode + chunk≠parallel |
| Q5 | `SKILL.md` / `task-authoring.md` | 路由指针 |
| Q6 | 根 `AGENTS.md` / `llmanspec/AGENTS.md` | Hard Rules / 主线摘要末尾短指针 |

| # | 其它 | 建议 |
|---|------|------|
| （可选） | Python 细缓存扩展 | 有产品需求再开独立 propose；**不删** YAML `none/preload_forever` |
| （明确不做） | 迁出 `lookup_chunk_size` | 与 c30 / 0.10 冲突 |

曾草案过独立 docs change，已弃用（文档-only 不进 `llmanspec/changes/`）。

## 非目标

- 实现迁移或 deprecation 警告（除非另开子 change）。
- 与已归档 c10/c20/c30 实现纠缠。
- 本目录改 live `llmanspec/specs/**`（无 Branch binding）。
