# Design: YAML vs Python policy boundary（c40）

## 范围

本 change：**盘点 + 原则 + follow-up 列表**。不改 `src/scalim` schema，不 `change start` 除非升格 Full。

交付物：

- `inventory.md`（R1）
- 本节 R2 原则
- 下方 R3 follow-up

## 与 c30 的关系

- c30 **保留** `sources.*.lookup_chunk_size`（keys 分片大小）。
- c30 **不**新增 YAML 并行键；并行 = Python opt-in。
- 本调研 **确认** 该键中长期仍属 YAML 可声明的「需求侧上限提示」，**不**开迁出 follow-up（除非未来有强证据证明它更像宿主调优）。

## R2 边界原则（草案，本阶段仅文档）

1. **MUST 留 YAML**：数据流图与资源身份——`runs`/deps、`main_source`/`sources` 身份与 loader 引用、`fields`/`relations`、`resources.*.id+path`、`outputs.to`/`fields`/`where`/`aggregate`、内容字段与 `params` 指令节点。
2. **MUST 仅 Python（已落地）**：并发与 worker、loader retry、guardrails、demand/workflow failure diagnostics、book **write strategy**（`BookWritePolicy`）、workflow `cache_pool` / `resources_wait`、observers/viz、security allowlist、`init_vars`。
3. **SHOULD 仅 Python**：与宿主/环境强相关、写入后难复现的调优（batch_size、max_workers、parallelize_*）。已迁出的不得回流 YAML。
4. **允许 YAML 可选提示 + Python 覆盖**：`lookup_chunk_size`（分片**大小**提示；并行另开 Python）；`cache_mode` 粗枚举；`outputs.*.write` 仅 header 局部行为。Python 不得靠「静默忽略 YAML」改变语义而不文档化。
5. **禁止**：未完成 inventory 就删 YAML 键；把编排/内容键误迁 Python；复活已删除的 budget / Dedup / TwoStage / `write_defaults`。
6. **第一刀默认**：文档 + agent/skill 对齐；不做 breaking deprecation，除非独立 propose 带兼容窗。

对照：`AGENTS.md` Hard Rules（YAML vs book write Python SSOT）、capability-matrix、c30 例外。

## R3 延后提案

| # | 标题（候选） | 范围 | 建议 |
|---|--------------|------|------|
| 0 | — | — | **结论：暂不迁**残留争议键；本 draft 以 inventory + 原则收口 |
| （可选）1 | `c41-yaml-policy-boundary-docs` | AGENTS/user-guide/capability-matrix 交叉链到本 inventory；agent skill 一页「别把 cache_mode 当 parallel」 | 低成本、可做 |
| （可选）2 | `c4x-cache-mode-python-extensions` | 仅**扩展** Python 细缓存策略；**不删** YAML `none/preload_forever` | 有产品需求再开 |
| （明确不做） | 迁出 `lookup_chunk_size` | 与 c30 冲突；下游 SQL IN 上限常跟 demand 走 | 拒绝除非重开调研 |

## 非目标

- 实现迁移或 deprecation 警告（除非另开子 change）。
- 与 c10/c20/c30/c50 实现纠缠。
- 改 live `llmanspec/specs/**`（无 Branch binding）。
