---
depends_on: []
---

# Draft change: YAML 编排 vs Python runtime policy 边界收紧

> **状态**：规划壳 / **调研任务草稿**（尚未 `change start`）。供后续 agent 承接盘点与提案细化；**不**在本目录直接改 schema。
> **触发来源**：c30 dig — 用户希望减少 YAML 中非「数据流/关系编排」的配置，迁到 Python policy。

## Why（调研动机）

仓库硬规则已倾向：

- YAML DSL：**编排 + 资源身份**（runs / deps / `resources.*.id+variant+path` / outputs…）
- Python：**写策略 / runtime policy**（例：book write policy SSOT）

但仍有若干 YAML 键偏 **调优 / 限流 / 宿主策略**（例：`sources.*.lookup_chunk_size`），与「图结构」混在同一 authoring 面。长期会导致：DSL 面膨胀、迁移叙事分裂、与 c30「分片大小可 YAML、并行许可只 Python」同向压力不一致。

本 draft **不实现迁移**；只定义调研范围与交付物，供后续 agent 产出正式 propose 或明确「暂不迁」。

## What（调研任务，给后续 agent）

### 任务 R1 — 盘点分类

扫描 YAML schema / capability-matrix / IR，把键标成三类（可微调标签，但须 SSOT 表）：

| 类 | 含义 | 例 |
|----|------|----|
| **编排/身份** | 数据流、依赖、资源 id/path、写出目标 | `runs`、`relations`、`resources.books.*.path` |
| **策略/调优** | 并发、分片、缓存模式、预算类残留 | `lookup_chunk_size`、部分 `cache_mode`、… |
| **内容/映射** | 字段计算、绑定、转换（通常应留 YAML） | `fields.*`、`bind`、`compute`/`call_by` |

交付：`inventory.md`（或 design 附表）——每键：类、出现位置、是否已有 Python 覆盖面、迁移成本粗估（低/中/高）。

### 任务 R2 — 边界原则草案

写清 MUST/SHOULD（进未来 capability 或 AGENTS 指针，**本阶段只写在本 change design**）：

- 哪些必须留 YAML；哪些 SHOULD 仅 Python；哪些允许「YAML 可选提示 + Python 覆盖」。
- 与已有例外对齐（book write policy、c30 opt-in、EXP env 等）。
- **禁止**在本调研阶段静默删 YAML 键。

### 任务 R3 — 迁移窗口与非目标

- 列出 0～3 个值得立项的 follow-up change（含是否动 `lookup_chunk_size`）。
- 明确非目标：不借机大改 DSL 语法；不把字段计算迁出 YAML；不阻塞 c10/c20/c30。

## Capabilities（预期，落地时再定）

### New Capabilities

- （可能）`yaml-runtime-policy-boundary`：authoring vs policy 分类与迁移合约（仅当 R2 结论要进 live specs）。

### Modified Capabilities

- （可能）docs：user-guide / capability-matrix / AGENTS Hard Rules 指针。

## Impact（调研期）

- **兼容**：本 draft 零代码、零 schema 变更。
- **后续若迁移**：须独立 propose + 兼容窗口；`lookup_chunk_size` 现状见 c30（**保留** YAML，并行开关在 Python）。

## Ethics

- `ethics.risk_level`: low（调研）/ medium（若后续删键）
- `ethics.prohibited_actions`: 未盘点完就删 YAML 键；把编排类键误迁 Python
- `ethics.required_evidence`: R1 清单 + R2 原则 + R3 follow-up 列表
- `ethics.refusal_contract`: 无库存清单不得开始删键实现
- `ethics.escalation_policy`: 与 runtime-policy-boundary / 用户迁移成本冲突时升级确认

## Open Questions（留给承接 agent）

1. `cache_mode` / `params` 模板等边缘键如何归类？
2. workflow 节点级 options 与 demand 级 YAML 是否同一套原则？
3. 第一刀是否只做文档+警告，不做 breaking？
