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
  - `src/scalim/dsl/by_yaml/runtime/workflow_execute.py`（workflow 侧数据流编排/生命周期）
  - `src/scalim/execution/run_ir.py`（将 `main_rows`/中间态注入到 demand 执行边界，或引入等价的显式契约）
  - `openspec/specs/workflow-cache-pool/spec.md`
  - `openspec/specs/source-cache/spec.md`
  - 可能新增的 `openspec/specs/workflow-intermediate-store/spec.md`
- SSOT / 生成物边界：
  - 当前位于 `openspec/notplan-changes/c999-workflow-intermediate-store-optimizations/`，仅维护 proposal 与契约草案：
    - `openspec/notplan-changes/c999-workflow-intermediate-store-optimizations/proposal.md`
    - `openspec/notplan-changes/c999-workflow-intermediate-store-optimizations/specs/workflow-intermediate-store/spec.md`
  - 不涉及 `.gen.*` 文件或 `AUTOGEN` 注入区块；共享前仍通过 `just openspec-check` 校验
