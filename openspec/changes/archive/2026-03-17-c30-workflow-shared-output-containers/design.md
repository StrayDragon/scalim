## Context

系统已经能在单个 demand 内通过 `outputs[*]` 支持单/多 sheet 输出，也能通过 workflow 并发执行多个 demand。
但在“多 demand 合并到同一个最终 workbook/csv”的场景下，workflow 缺少：

- 共享输出容器（resources）的声明与生命周期管理
- 写入/合并语义（append/字段对齐/header 策略）
- 对共享资源的确定性写入顺序与互斥（不得依赖并发完成时序）

结果是用户只能回到 Python glue 或中间文件拼接，不利于复用、对拍与 scalim-viz 可视化表达。

本 change 依赖：

- `workflow-ir-roadmap`：Workflow IR 与调度底座（节点系统 + 确定性）
- `workflow-dag-context-passing`：DAG 调度/compile-on-ready（为 write nodes 依赖 demand outputs 提供统一机制）
- `workflow-observability-bridge`：workflow-level 事件与归因字段（资源生命周期可观测）

## Goals / Non-Goals

**Goals:**

- 在 workflow 层声明共享输出资源（workbook/csv），由 workflow runtime 统一创建/关闭/commit/discard
- 将写入共享资源的动作建模为显式 workflow node 类型：`write_sheet` / `append_sheet`
- 定义确定性写入顺序：对同一共享资源串行写入，顺序以 workflow YAML 的 runs 列表顺序为 SSOT
- 定义 append/merge 语义：字段对齐与 header 策略明确、可配置、可测试
- 定义默认落盘语义：延迟 commit + 原子落盘；失败默认 discard，避免部分提交灰区
- 与可观测性桥接对齐：资源 create/write/commit/discard 事件可 join 回 workflow DAG

**Non-Goals:**

- 不支持跨进程/分布式资源共享
- 不在本 change 内引入“大体量 in-memory dataset 传递”（写入节点消费 artifacts/输出目标；ctx 仅承载小摘要）
- 不替代 demand 内部的 `outputs[*]` 能力（workflow 侧只解决跨 demand 合并）

## Decisions

### 1) Authoring surface：简写允许，但语义必须解糖为显式 write nodes

YAML 可以提供直觉写法（例如 `runs[*].write_to`），但编译后 MUST 解糖为独立的 write nodes：

- 便于对共享资源做互斥与确定性顺序控制
- 便于表达依赖（write node depends_on demand node output）
- 便于对资源生命周期发出 workflow-level 事件（create/write/commit/discard）

### 2) 资源声明与 IR 结构

Workflow IR 需要新增（或填充）：

- `WorkflowResourceIr`：资源 id、类型（workbook/csv）、路径与配置（header_fields_output_by、lock 等）
- `WriteSheetNodeIr` / `AppendSheetNodeIr`：资源引用、目标 sheet、输入 output 引用、合并策略

### 3) WriteCoordinator：互斥 + 确定性

对同一资源的写入必须串行化：

- 同一 workbook/csv 在任一时刻只能有一个写入 node 执行写操作
- 写入顺序以 workflow 声明顺序为 SSOT（不得依赖并发完成时序）

实现上可通过“资源锁 + 声明顺序队列”实现。

### 4) 合并语义（append/merge）

最小可落地的合并能力：

- **workbook 多 sheet**：每个 node 写不同 sheet（无合并，仅需冲突策略）
- **append 到同一 sheet**：明确字段对齐与 header 策略

默认策略建议：

- 字段对齐按 field_id（更接近 DSL 的稳定标识）
- header 仅输出一次（首次写入时输出）
- 字段不匹配默认 fail-fast（并提供可配置的 warn/skip 用于迁移窗口）

### 5) 落盘语义：延迟 commit + 原子替换

- workflow 结束前资源处于“未提交”状态（写入发生在临时对象/临时路径或缓冲区）
- workflow 成功：统一 commit，并原子落盘/替换最终文件
- workflow 失败：默认 discard，不产生“已提交但不完整”的最终文件

### 6) 观测集成

资源生命周期必须可观测，并复用统一归因字段。v0 事件类型固定为:

- `workflow_resource_create`
- `workflow_resource_write`（每个 write_sheet/append_sheet 节点至少发出一次）
- `workflow_resource_commit`
- `workflow_resource_discard`

事件 payload MUST 包含 `resource_type` / `resource_id` / `path`(若存在) 等可诊断字段,并携带 `workflow_exec_id` / `workflow_node_id` 便于 join 回 DAG。

## Risks / Trade-offs

- [写入串行导致吞吐下降] → 仅对同一资源串行；不同资源可并行；优先保证确定性与正确性
- [失败清理复杂] → 默认延迟 commit + 失败 discard；避免“部分提交”语义讨论
- [字段对齐策略争议] → 先提供严格默认（fail-fast）+ 可配置策略，迁移窗口可 warn/skip

## Migration Plan

- 不声明 resources 时 workflow 行为不变
- 迁移路径：
  1. 先支持 workbook 多 sheet（最直觉、风险最小）
  2. 再支持 append 到同一 sheet/csv（引入字段对齐与 header 策略）

## Final Decisions (no open questions)

- merge/write 仅承载“表格值写入”语义:
  - 不在本 change 内保留/复制 Excel 公式、样式、合并单元格等富格式能力
  - 如上游 demand 输出依赖样式/公式,必须在单 demand 内完成最终落盘,不得参与 workflow-level merge
- sheet 名必须显式指定:
  - v0 不提供默认 sheet 命名模板
  - 发生 sheet 名冲突时按 `sheet_conflict_policy` 处理（默认 fail-fast）

## Docs / Generated Boundaries

- SSOT:
  - workflow schema DSL: `src/scalim/dsl/by_yaml/schema_dsl/**`
  - workflow runtime: `src/scalim/dsl/by_yaml/runtime/**`
- Generated（禁止手改）：
  - `src/scalim/dsl/by_yaml/schema/workflow.gen.json`（通过 `just gen-yaml-dsl-schema` 生成）
  - docs 中的 `.gen.` 与 injected blocks（通过 `just gen-docs` 生成）
- Drift / gates：
  - `just qa`
  - `just openspec-check`
