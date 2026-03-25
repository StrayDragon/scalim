## Why

`workflow-intermediate-store` 先解决最急迫的 pathless CSV 临时落盘问题，但 workflow 与 demand 之间仍存在更大的优化空间：内存预算治理、spill 策略、跨 demand 的 source 复用，以及非 CSV 中间态的统一承载。这些方向值得单独建模，否则很容易把 v1 简化方案膨胀成一轮高风险大改。

因此需要一个低优先级、仅做 proposal 的后续提案，收敛这些优化目标与边界，避免它们在当前变更中以“顺手加入”的形式失控扩张。

## What Changes

- 规划一套更通用的 workflow intermediate store，覆盖：
  - 内存预算与观测
  - 超限后的 fail-fast / spill 策略
  - 跨 demand 节点的 source / preload 结果复用
  - 非 CSV 中间态（例如更适合 columnar 或自定义结构的中间格式）
- 在 `workflow-intermediate-store` 已引入的 `InMemoryCsv`（字符串化 CSV 语义）之外，新增一个独立的 typed artifact：`InMemoryRows`（保留 Python `FieldValue` 类型域），用于：
  - workflow 内部的纯 Python 数据流（source）传递
  - 需要保留数值/布尔/Decimal 等类型语义的后续消费（例如 workbook 写入、进一步计算）
  - 与 `InMemoryCsv` 并存但互不干扰：两者面向不同场景，不互相倒逼对方的契约扩张
- 评估这套能力与现有 `workflow-cache-pool`、`source-cache`、output composition、workflow artifacts/ctx 的职责边界，避免能力重叠。
- 该 change 当前只建立 proposal（可选补充最小 specs 作为契约草案），不开始实现。

## Capabilities

### New Capabilities
- `workflow-intermediate-store`: 规划 workflow 级中间态存储抽象，支持内存对象、预算治理与可选 spill。
- `workflow-source-reuse`: 规划多个 demand 节点之间对相同 source / preload 结果的复用与生命周期管理。
- `workflow-intermediate-artifacts`: 规划 workflow 中间态产物的“稳定数据契约”，至少包括：
  - `InMemoryCsv`：与 CSV 文件输出等价的字符串化表结构
  - `InMemoryRows`：保留 `FieldValue` 类型域的行式/表式结构（用于纯 Python 数据流）
- `workflow-dataflow-main-rows`: 规划将上游节点的 `InMemoryRows` 作为下游节点的 `main_rows` 输入（显式声明、显式授权），形成 workflow 内纯 Python 数据流（source）传递。

### Modified Capabilities
- `workflow-cache-pool`: 明确它与更通用 intermediate store 的边界，避免 cache_pool 被继续扩展成“万能中间态容器”。
- `source-cache`: 评估 source 级缓存是否需要与 workflow 级 intermediate store 形成衔接。
- `output-composition`: 评估除 CSV 之外的中间输出如何与 output composition / sink 装配协同。

## Impact

- 该 proposal 面向后续路线，不改变当前实现，也不修改现有 YAML authoring surface。
- 后续若继续推进，影响面预计会覆盖：
  - `src/scalim/execution/**`
  - `src/scalim/workflow/**`
  - `src/scalim/workflow/execute.py`（workflow 侧数据流编排/生命周期）
  - `src/scalim/execution/run_ir.py`（将 `main_rows`/中间态注入到 demand 执行边界，或引入等价的显式契约）
  - `openspec/specs/workflow-cache-pool/spec.md`
  - `openspec/specs/source-cache/spec.md`
  - 可能新增的 `openspec/specs/workflow-intermediate-store/spec.md`
- SSOT / 生成物边界：
  - 当前位于 `openspec/notplan-changes/c80-workflow-intermediate-store-optimizations/`，仅维护 proposal 与契约草案：
    - `openspec/notplan-changes/c80-workflow-intermediate-store-optimizations/proposal.md`
    - `openspec/notplan-changes/c80-workflow-intermediate-store-optimizations/specs/workflow-intermediate-store/spec.md`
  - 不涉及 `.gen.*` 文件或 `AUTOGEN` 注入区块；共享前仍通过 `just openspec-check` 校验

## Calibration Notes (2026-03-25)

- `c15-workflow-intermediate-store` 已完成归档（`openspec/changes/archive/2026-03-25-c15-workflow-intermediate-store/`），pathless CSV 临时落盘的基础能力已落地
- workflow 模块路径已从 `src/scalim/dsl/by_yaml/runtime/` 迁移到 `src/scalim/workflow/`，已校正 `workflow_execute.py` → `execute.py`
- `workflow-cache-pool`、`source-cache` 规范已存在于 `openspec/specs/`
- 本提案仍为纯路线规划文档,不涉及实现
<<<<<<<< HEAD:openspec/notplan-changes/c15-workflow-intermediate-store-optimizations/proposal.md
- c15 归档时的 delta specs 落入 `workflow-managed-temp-outputs`/`workflow-shared-output-containers`/`output-composition`,而非独立的 `workflow-intermediate-store` spec;如后续推进本提案,需决定是创建独立 spec 还是继续扩展已有 specs

## Implementation Pitfalls (代码探索 2026-03-25)

### P1: `InMemoryCsv` 已实现但是纯字符串语义

`sinks/sink_csv.py` 中 `InMemoryCsv` 为 `header: List[str]` + `rows: List[List[str]]`。下游节点需要 typed 值必须自行解析字符串,与 proposal 设想的 `InMemoryRows`（保留 `FieldValue` 类型域）形成两套独立体系。需明确两者的边界:InMemoryCsv 面向 CSV 输出等价,InMemoryRows 面向计算/workbook。

### P2: `run_ir` 不传 `main_rows` 到 engine

当前 `execution/run_ir.py` 调用 `engine.run(sink=...)` 不传递 `main_rows` 参数,虽然 `ScalimEngine.run` 签名已支持 `main_rows`。实现"上游 InMemoryRows 作为下游 main_rows"需要在 `run_ir` 层新增参数传递和 `ExecutionRequest` 扩展。

### P3: `WorkflowCtxStore` 有 JSON-like 和字节限制

`workflow/ctx.py` 的 `WorkflowCtxStore` 强制 `ensure_json_like` 和字节上限检查。typed row table 无法通过 ctx 传递,只能走 `WorkflowArtifactsDirectory` 的 artifact 路径——这意味着需要新增 artifact 类型并完善 publish/get/discard 生命周期。

### P4: artifact 生命周期管理压力

`WorkflowArtifactsDirectory` 已有 `discard_in_memory_csv_output`/`discard_all_in_memory_csv_outputs`。每种新 artifact 类型（InMemoryRows 等）需要对应的 discard/publish/visibility 逻辑,且需与 `visible_producer_node_ids` 依赖检查对齐,否则跨节点内存泄漏。

### P5: `workflow/artifacts.py` 和 `workflow/ctx.py` 是薄封装

实际 artifact/ctx 行为逻辑在 `workflow/execute.py` 中。修改 intermediate store 需直接改动 execute.py 的编排逻辑,而非仅在 artifacts/ctx 模块中扩展。
========
>>>>>>>> f169a62 (Squash commits from feat-yaml-dsl-public-tools):openspec/notplan-changes/c80-workflow-intermediate-store-optimizations/proposal.md
