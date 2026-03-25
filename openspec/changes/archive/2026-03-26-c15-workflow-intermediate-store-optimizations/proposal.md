## Why

`workflow-intermediate-store` 的 v1 先解决最急迫的 workflow-managed pathless CSV 临时落盘问题，但 workflow 与 demand 之间仍有两个关键缺口未闭合：

- 缺少稳定的 typed 中间态契约：当前仅有字符串化的 `InMemoryCsv`，无法承载 `FieldValue` 类型域，typed 数据流只能靠下游自行 parse。
- workflow 无法把上游节点的数据作为下游 demand 的 main source：尽管 engine 层支持 `main_rows` 注入，但 workflow 层缺少显式声明与稳定 wiring。

这两点会逼迫用户回退到“落盘 + 重新加载/解析”或“ctx/临时对象塞进隐式通道”的非理想路径，既慢也不稳。

因此需要把 “typed 中间态 + workflow 纯 Python dataflow” 作为一个独立切片落地实现，并明确边界（不做预算/spill 等更大议题），避免 v1 在后续迭代中以“顺手加入”的形式失控扩张。

## What Changes

- 在 `workflow-intermediate-store` 已引入的 `InMemoryCsv`（字符串化 CSV 语义）之外，新增一个独立的 typed artifact：`InMemoryRows`（保留 `FieldValue` 类型域），用于 workflow 内部的纯 Python 数据流（source）传递与后续 typed 消费。
- 扩展 execution 编排：`run_ir` 透传 `main_rows` 到 engine，并提供可选的 typed rows 捕获通道（按需启用）。
- 扩展 workflow YAML/IR：通过显式声明 `main_rows_from` 将上游 `InMemoryRows` wiring 到下游 demand 的 `main_rows`（显式依赖/显式授权）。
- workflow runtime 增加 typed artifact 的发布/可见性检查/最终 consumer 释放语义（与 workflow-managed CSV 的生命周期模式对齐）。

**Non-Goals（本 change 不做）**
- 不引入内存预算、spill-to-disk/tmpfs、LRU、OOM 防护等“预算治理”机制（另开 change 单独建模）。
- 不引入非 rows 的 columnar/自定义格式（parquet/arrow/sqlite 等）。
- 不改变 demand YAML 的既有 authoring surface（仅扩展 workflow YAML；standalone demand 规则不放宽）。

## Capabilities

### New Capabilities
- `workflow-intermediate-store`: 提供 workflow 级 typed 中间态 `InMemoryRows`，以及发布/可见性/生命周期（最终 consumer 释放）语义。
- `workflow-intermediate-artifacts`: 提供 workflow 中间态产物的“稳定数据契约”，至少包括：
  - `InMemoryCsv`：与 CSV 文件输出等价的字符串化表结构
  - `InMemoryRows`：保留 `FieldValue` 类型域的行式/表式结构（用于纯 Python 数据流）
- `workflow-dataflow-main-rows`: 支持将上游节点的 `InMemoryRows` 作为下游节点的 `main_rows` 输入（显式声明、显式授权），形成 workflow 内纯 Python 数据流（source）传递。

### Modified Capabilities
- `workflow-cache-pool`: 明确它与更通用 intermediate store 的边界，避免 cache_pool 被继续扩展成“万能中间态容器”。
- `source-cache`: 评估 source 级缓存是否需要与 workflow 级 intermediate store 形成衔接。
- `output-composition`: 评估除 CSV 之外的中间输出如何与 output composition / sink 装配协同。

## Impact

- 该 change 将落地实现（不止 proposal），但 **不会** 修改 demand YAML authoring surface；会扩展 workflow YAML authoring surface。
- 影响面预计覆盖：
  - `src/scalim/execution/**`
  - `src/scalim/workflow/**`
  - `src/scalim/workflow/execute.py`（workflow 侧数据流编排/生命周期）
  - `src/scalim/execution/run_ir.py`（将 `main_rows`/中间态注入到 demand 执行边界，或引入等价的显式契约）
  - `openspec/specs/workflow-cache-pool/spec.md`
  - `openspec/specs/source-cache/spec.md`
  - 可能新增的 `openspec/specs/workflow-intermediate-store/spec.md`
- SSOT / 生成物边界：
  - 本 change 工件位于 `openspec/changes/c15-workflow-intermediate-store-optimizations/`。
  - 不手改任何 `.gen.*` 文件或 `AUTOGEN` 注入区块；需要生成物更新时按 SSOT 流程通过 `just gen-docs`/`just qa` 完成。
  - 共享前通过 `just openspec-check` 与 `just qa` 作为门禁。

## Calibration Notes (2026-03-25)

- `c15-workflow-intermediate-store` 已完成归档（`openspec/changes/archive/2026-03-25-c15-workflow-intermediate-store/`），pathless CSV 临时落盘的基础能力已落地
- workflow 模块路径已从 `src/scalim/dsl/by_yaml/runtime/` 迁移到 `src/scalim/workflow/`，已校正 `workflow_execute.py` → `execute.py`
- `workflow-cache-pool`、`source-cache` 规范已存在于 `openspec/specs/`
- 本 change 将推进实现（typed artifact + workflow dataflow），并以 `just qa` 为兜底门禁
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
