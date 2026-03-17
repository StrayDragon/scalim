## 1. IR 数据结构

- [x] 1.1 定义 `WorkflowIr` / `WorkflowNodeIr` / `WorkflowEdgeIr` / `WorkflowOptionsIr` 的最小字段集合（Python 3.6 兼容）
- [x] 1.2 定义节点类型枚举：`demand`（v0）+ 预留 `write_sheet`/`append_sheet`/`condition`/`selector`
- [x] 1.3 定义 artifacts 目录与可见性校验规则（显式 deps + 显式 artifacts）

## 2. Workflow 编译器（结构编译）

- [x] 2.1 实现 workflow YAML → `WorkflowIr`（解析 runs/options/resources 的 v0 结构）
- [x] 2.2 实现静态校验：id 唯一、deps 合法、无环、artifact 引用不越界
- [x] 2.3 生成确定性顺序（ready tie-break 与 outcomes 对齐的 SSOT）

## 3. 调度器（执行 IR）

- [x] 3.1 实现确定性 DAG 调度（ready 队列 + tie-break）
- [x] 3.2 实现节点状态机（pending/ready/running/done/failed/cancelled）
- [x] 3.3 适配 failure_policy（all_fail/primary_only）并保证 outcomes 顺序稳定

## 4. 入口迁移与对拍

- [x] 4.1 在不改变对外入口的前提下，将 `run_workflow()` 内部逐步迁移为“编译 YAML → IR → 执行”
- [x] 4.2 集成测试：与旧实现行为等价（结果顺序、失败策略、并发边界）

## 5. 文档/门禁

- [x] 5.1 明确生成物边界：不手改任何 `.gen.*` / injected blocks；需要时通过既有入口生成
- [x] 5.2 运行 `just qa`
- [x] 5.3 运行 `just openspec-check`
