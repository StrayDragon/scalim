## 1. Workflow IR：资源与写出节点

- [x] 1.1 扩展 workflow YAML：支持 `workflow.resources`（workbooks/csvs）与 `runs[*].write_to`（workbook_sheet/workbook_append/csv_append）
- [x] 1.2 定义 `WorkflowResourceIr`（资源 id/type/path/options）
- [x] 1.3 定义 `WriteSheetNodeIr` / `AppendSheetNodeIr`（输入 output 引用 + 合并策略）

## 2. ResourceManager

- [x] 2.1 实现资源生命周期管理：create/lock/commit/discard
- [x] 2.2 默认延迟 commit + 原子落盘；失败默认 discard（避免部分提交）

## 3. WriteCoordinator（确定性写入）

- [x] 3.1 实现对同一资源的互斥/串行写入
- [x] 3.2 写入顺序以 workflow 声明顺序为 SSOT（不得依赖并发完成时序）

## 4. 合并语义（append/merge）

- [x] 4.1 实现字段对齐策略（默认按 field_id 且严格；可配置 warn/skip）
- [x] 4.2 实现 header 输出策略（默认仅一次）
- [x] 4.3 实现 sheet 冲突策略（`error|overwrite|skip`；默认 `error`）

## 5. 观测与诊断

- [x] 5.1 发出资源生命周期事件：`workflow_resource_create` / `workflow_resource_write` / `workflow_resource_commit` / `workflow_resource_discard`（复用 `workflow_exec_id` / `workflow_node_id`）
- [x] 5.2 错误诊断：字段对齐失败、sheet 冲突、资源锁失败需包含差异/上下文摘要

## 6. 测试与门禁

- [x] 6.1 测试：多 sheet、append 合并、写入顺序确定性、失败清理
- [x] 6.2 更新 workflow schema SSOT（`src/scalim/dsl/by_yaml/schema_dsl/**`）并运行 `just gen-yaml-dsl-schema`（禁止手改 `src/scalim/dsl/by_yaml/schema/workflow.gen.json`）
- [x] 6.3 如涉及 docs/注入块,更新 SSOT 并运行 `just gen-docs`（禁止手改 `.gen.` 与 injected blocks）
- [x] 6.4 运行 `just qa`
- [x] 6.5 运行 `just openspec-check`
