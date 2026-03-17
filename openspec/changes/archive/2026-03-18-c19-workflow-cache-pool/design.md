## Context

当前 workflow 的跨 runs 共享缓存只有一个开关：`options.share_preload_cache: bool`，用于“跨 runs 共享 `cache_mode: preload_forever` 的预加载缓存”。该设计把多个维度揉成了一个二元开关：

- 共享范围：哪些 sources 该共享？共享到 workflow 末尾还是用完即释放？
- 一致性/冲突策略：同一 `source_id` 在不同 runs 的 preload 规格不一致时如何处理？
- 内存策略：缓存容量、生命周期、淘汰与可观测性如何治理？

同时，现有实现强依赖“启动前全量编译 + 全量预检”的假设，这与后续 DAG/ctx/compile-on-ready（workflow-dag-context-passing）天然冲突：部分 signature 只有在 node 就绪并渲染完 params 后才可确定。

## Goals / Non-Goals

**Goals:**

- 定义 workflow-scope cache pool：signature-keyed entries + 生命周期管理 + 预算/淘汰策略
- 明确 signature 的可复现计算方式：基于 **已渲染的 params**（含 `{$init_var: ...}` / `{$ctx: ...}`），避免模板级复用误伤
- 在具备 Workflow IR/DAG 信息时，支持 DAG-based refcount（提前释放内存）
- 明确冲突策略：`error` / `separate` / `warn`（行为可测试、错误可诊断）
- 与可观测性桥接（workflow-observability-bridge）对齐：提供 acquire/release/evict 事件点，并复用 `workflow_exec_id` / `workflow_node_id`

**Non-Goals:**

- 不做分布式缓存（跨进程/跨机器）
- 不在本 change 内实现 dataset/index 工件复用（cache pool 只作为其内存治理底座）
- 本 change 明确锁定最小 YAML authoring surface（`options.cache_pool`），以支持仓内一次性升级与实现落地

## Decisions

### 1) CachePool 的最小接口形态

cache pool 的核心能力拆为三类动作：

- **Acquire**：为某个 signature 获取（可能创建）缓存条目，并递增引用
- **Release**：node 完成或不再需要时递减引用
- **Evict/Discard**：在预算策略驱动下淘汰 refcount=0 的条目（或在 workflow 结束时统一清理）

实现上可提供组合 API（如 get_or_load），但语义上必须可分解为 acquire/release/evict。

### 2) Signature 计算：以“已渲染 params”为 SSOT

signature MUST 可复现且 JSON-safe，并至少包含：

- kind（preload_forever / dataset_index / …）
- `source_id`（或 artifact id）
- loader 引用（以及会影响结果形状的上下文：normalize/lookup_cast/key 等）
- **rendered_params**（已解析 init_vars/ctx 指令）
- 可选：loader_call_context（当其会改变输出形状或缓存隔离边界时）

原则：模板不同但渲染后等价 → 允许复用；模板相同但渲染后不同 → 禁止复用。

### 3) 冲突策略：error/separate/warn

当同一个逻辑 key（例如同一 `source_id`）出现多个不同 signature 时：

- `error`：fail-fast，并提供差异摘要（默认/严格）
- `separate`：允许并行存在多个 entries，互不复用（迁移窗口/避免误伤）
- `warn`：继续执行但产生可观测告警（仅用于 debug/迁移窗口）

### 4) 生命周期：DAG-based refcount + pin

- 在具备 Workflow IR/DAG 信息时，refcount MUST 来自 IR 的 consumer set 推导（上界），并随 node 完成递减
- 释放条件：refcount 归零 → 释放（或进入可淘汰状态）
- `pin` 作为 escape hatch：强制条目常驻到 workflow 结束（用于某些必须在尾部使用/复用的场景）

### 5) 预算与淘汰策略

cache pool MUST 支持预算配置（v0 仅要求 `max_entries`）。当超限时必须有明确策略：

- fail-fast（严格护栏）
- 淘汰（例如 LRU，但不得淘汰 refcount>0 的条目）

### 6) compile-on-ready 下的冲突校验与观测

在 compile-on-ready 模型下：

- 全量预检不再是硬前置；冲突检测应以“首次写入/首次 acquire”为边界增量发生
- 所有 acquire/release/evict 行为必须可观测，并复用 `workflow_exec_id` / `workflow_node_id` 归因，便于解释“为何没有 loader_call”

## Risks / Trade-offs

- [signature 漂移] 过多字段会导致复用率低；过少字段会导致复用错误 → 以 spec 列出的最小集合为底线，并对“会影响结果形状”的字段做清单化
- [refcount 推导不精确] 静态推导可能高估但不应低估 → 允许高估（晚释放），禁止低估（提前释放导致错误）
- [预算估算不准] bytes 估算困难 → 允许先以 entries/简化估算落地，并通过观测迭代

## Migration Plan

- breaking：`options.share_preload_cache` 被移除，演进为结构化的 `options.cache_pool`
- 仓内 workflow YAML 一次性升级到新字段（不保留旧字段兼容兜底）
- 增量期可用 `conflict_policy=separate/warn` 降低误伤，最终收敛回 `error`

## Final Decisions (no open questions)

- signature 不纳入“跨环境版本”信息：cache pool 为**单次 workflow 执行内**的内存结构,不跨进程/跨调用复用,因此不需要为跨环境复用兜底
- 预算治理以 `max_entries` 为 v0 SSOT；更细粒度的 bytes 预算若需要,将以独立变更引入并给出可复现的估算口径

## Docs / Generated Boundaries

- SSOT:
  - workflow schema DSL: `src/scalim/dsl/by_yaml/schema_dsl/**`
  - workflow runtime: `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py`
- Generated（禁止手改）：
  - `src/scalim/dsl/by_yaml/schema/workflow.gen.json`（通过 `just gen-yaml-dsl-schema` 生成）
  - docs 中的 `.gen.` 与 injected blocks（通过 `just gen-docs` 生成）
- Drift / gates：
  - `just qa`
  - `just openspec-check`
