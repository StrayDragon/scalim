## Why

我们希望覆盖 4 类导出形态:

1) 单 demand 单 sheet 导出  
2) 单 demand 多 sheet 导出  
3) 多 demand 单 sheet 导出  
4) 多 demand 多 sheet 导出

当前系统已经能在单 demand 内通过 `outputs[*]` 支持单/多 sheet,workflow 也能批量并发跑多个 demand。
但在 **多 demand 合并到同一个最终 workbook/csv** 的场景下,workflow 仍缺少“共享输出容器 + 合并语义 + 确定性调度”的抽象,用户只能回到 Python glue 或中间文件拼接,不利于复用、对拍与 scalim-viz 的可视化表达。

## What Changes

说明: 本 change 建立在 `workflow-ir-roadmap` 的 workflow IR/节点系统之上(以 output/resource 节点表达),避免在现有 `run_workflow()` 直接执行器上引入不可扩展的特例。

- **New**: workflow 级“共享输出容器”(resources)概念,用于多 demand 合并输出
  - 例如声明一个共享 workbook/csv 资源,由 workflow 统一创建/关闭/落盘(只保存一次,原子替换)
  - 多个 demand 的输出目标不再各自写文件,而是通过 workflow 的写出节点写入共享容器

- **New**: 将 workflow 视为 DAG 编排的一种承载(“demand 只是节点类型之一”)
  - `demand` 节点: 运行一个 demand(可并发),产出可引用的 artifacts(例如某个 output_target),并发布轻量 ctx 摘要(例如 output_path/total_rows)
  - `write_sheet`/`append_sheet` 节点: 将一个或多个 demand 的输出写入共享 workbook/csv

- **New**: 多 demand → 单 workbook 多 sheet 的直觉写法
  - 支持把每个 run 的某个 output 写到一个 sheet
  - sheet 名 MUST 显式指定；当发生冲突时按可配置策略处理(error/overwrite/skip)

- **New**: 多 demand → 单 sheet 的合并/追加语义
  - append 模式(行追加)为优先落地目标
  - 需要明确字段对齐策略(按 field_id 对齐/按 header 对齐/严格相等)与 header 输出策略(一次/每段)
  - 需要确定性顺序(以 workflow 声明顺序为准,不得依赖并发完成顺序)

- **Non-breaking**: 不配置新字段时,保持现有 workflow 语义不变

### Recommended Direction (MVP)

- 该 change 推荐建立在 `workflow-dag-context-passing` 之上(同一套 DAG 调度 + ctx),优先落地 **workbook 多 sheet** 与 **csv append** 两条路径。
- MVP 优先选择“按资源互斥串行写入”的路线(避免在 workflow 内引入大体量 in-memory dataset 传递)：
  - 多个 run 可以并发编译/执行,但对同一共享资源(workbook/csv)的写入 MUST 串行化并遵循声明顺序
  - 共享资源在 workflow 末尾统一 commit/原子落盘,失败时 MUST discard（不支持 partial commit,避免“部分写入但语义不清”的灰区）

- **SSOT**: 写出节点是独立 node 类型（不是 demand 的后处理）
  - YAML authoring surface 可提供 `runs[*].write_to` 等简写,但编译后 MUST 解糖为独立的 `write_sheet`/`append_sheet` 节点,以便：
    - 对共享资源做互斥/串行化与确定性顺序控制
    - 在 workflow-level 发出 resource 生命周期事件（create/write/commit/discard）并复用 `workflow_exec_id` / `workflow_node_id` 归因
    - 允许后续扩展“多输入合并/字段对齐策略/失败恢复”而不污染 demand 运行边界

### MVP Example (YAML)

```yaml
# yaml-language-server: $schema=../schema/workflow.gen.json

workflow:
  resources:
    workbooks:
      report:
        path: ./out/report.xlsx
  runs:
    - id: orders
      demand: ./orders.demand.yaml
      write_to:
        workbook_sheet:
          workbook: report
          sheet: Orders
          output: detail
    - id: customers
      demand: ./customers.demand.yaml
      write_to:
        workbook_sheet:
          workbook: report
          sheet: Customers
          output: detail
  options:
    max_concurrency: 4
    failure_policy: all_fail
```

## Capabilities

### New Capabilities
- （本提案优先作为对现有 workflow 能力的扩展,不新增独立 capability；若后续实现拆分范围再另起 change。）

### Modified Capabilities
- `yaml-dsl-workflow`: 扩展 workflow 的 schema 与语义,支持共享输出容器与跨 demand 合并写出(并定义确定性/并发/失败策略/冲突策略)

## Impact

- YAML authoring:
  - 用户可以用一份 workflow YAML 直观表达“多阶段流水线 + 最终合并输出”的需求
  - demand YAML 尽量保持不变;workflow 侧负责“资源与落盘”的编排
- Runtime:
  - 需要在 workflow 调度层引入资源生命周期管理(共享 workbook/csv)与写出节点的串行化/互斥
  - 需要补齐合并语义的静态校验与 fail-fast 错误(字段对齐、sheet 冲突、header 策略等)
  - 需要明确 `failure_policy` 在“部分节点已写出/尚未落盘”场景下的行为(建议默认延迟落盘以保持原子性)
- Viz:
  - workflow DAG 与资源/写出节点将更适合在 scalim-viz 上表达为“编排层视图”(便于排障与复用)

- Spec / schema / docs governance:
  - SSOT:
    - workflow schema DSL 与 hover 文案: `src/scalim/dsl/by_yaml/schema_dsl/**`
    - workflow runtime 行为: `src/scalim/dsl/by_yaml/runtime/**`
  - Generated（禁止手改）：
    - `src/scalim/dsl/by_yaml/schema/workflow.gen.json`（通过 `just gen-yaml-dsl-schema` 生成）
    - docs 中的 `.gen.` 与 injected blocks（通过 `just gen-docs` 生成）
  - Gates:
    - `just qa`
    - `just openspec-check`
