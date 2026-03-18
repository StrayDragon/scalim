## Why

当前 demand YAML 已支持 `workbook` 输出容器(多 sheet)，实现上通过 `ExcelWorkbookSink` 在内存中维护一个 `write_only` workbook，并在 `close()` 时一次性原子落盘；同时支持 `write_lock` 以 fail-fast 避免并发写同一路径导致损坏。

但在 workflow 演进到 DAG 编排 + 共享输出资源之后，仍缺少一个“可在内存中共享、且可作为输入/输出被节点引用”的 workbook 抽象：

- 多节点共享：跨 nodes 合并输出时，若仍让各 demand 各自写 xlsx，再做拼接，会引入中间文件与额外 IO；若多个 nodes 误写同一路径，当前只能在运行时靠写锁 fail-fast，错误时机与诊断都不理想。
- 作为输入：`ExcelWorkbookSink(write_only=True)` 不支持读取/二次加工；下游节点若想基于上游 workbook 内容再计算/追加，只能回到“落盘→再读”的低效路径。
- 语义统一：workflow 已在 `workflow-ir-roadmap`/`workflow-dag-context-passing` 中确立 artifacts/resources 的边界与生命周期治理方向；workbook 作为一个典型“大对象输出”，需要一个与之对齐的、可被 IR/调度/观测治理的抽象。

因此需要引入 workflow-level 的 **sheetbook**（内存工作簿）资源：可被多个节点写入/读取、可延迟导出为 xlsx、并具备预算与可观测性契约，从而把“Excel 作为文件格式”与“表格集合的中间表示”解耦。

## What Changes

- **New**: workflow-level `sheetbook` resources（内存工作簿）
  - 在 workflow 层声明 `sheetbook` 资源（资源本体仅在内存中存在；可选 `export_xlsx` 导出配置）
  - 支持多个 workflow nodes 写入/追加 sheet（确定性顺序，fail-fast 处理冲突）
  - 为内存占用提供预算护栏（max_sheets / max_total_cells；超限 fail-fast）

- **New**: `sheetbook` 作为节点间输入/输出的桥接能力（MVP）
  - 允许下游 demand 通过内置 loader 读取 sheetbook 中某个 sheet 的行数据（作为 source/main_source）
  - 强制依赖闭包可见性：仅允许读取 deps 可见范围内的上游 sheetbook

- **New**: 从 sheetbook 导出为 Excel workbook 的确定性落盘语义
  - 通过 sheetbook 资源的 `export_xlsx` 配置,在 workflow 成功结束时原子导出为 xlsx（失败默认 discard）
  - workflow 失败时 MUST 不产生“部分提交但不完整”的最终 xlsx（统一 discard）

- **New**: workflow 级别的 Excel 输出冲突预检（避免运行时锁冲突）
  - 当 workflow 并发执行多个 demand 时，系统 MUST 在“写入发生前”检测“多个 nodes 写同一路径”的情况并 fail-fast：
    - 若路径可静态提取,则结构编译阶段 fail-fast
    - 若路径依赖动态渲染,则在 node 物化编译后、实际写入前 fail-fast
  - 该预检提升确定性与诊断质量，避免依赖写锁的运行时不确定失败

### MVP Example (YAML)

```yaml
# yaml-language-server: $schema=../schema/workflow.gen.json

workflow:
  resources:
    sheetbooks:
      report:
        budget:
          max_sheets: 32
          max_total_cells: 5000000
        export_xlsx:
          path: ./out/report.xlsx
          write_lock: true

  runs:
    - id: extract_orders
      demand: ./extract_orders.demand.yaml
      write_to:
        sheetbook_sheet:
          sheetbook: report
          sheet: Orders
          output: detail

    - id: extract_customers
      demand: ./extract_customers.demand.yaml
      write_to:
        sheetbook_sheet:
          sheetbook: report
          sheet: Customers
          output: detail

    - id: build_summary
      demand: ./build_summary.demand.yaml
      depends_on: [extract_orders, extract_customers]
      # 下游 demand 通过内置 loader 读取 sheetbook rows;这里用 init_vars 注入引用,保持 demand YAML 可复用.
      init_vars:
        orders_sheet_ref: {node: extract_orders, sheetbook: report, sheet: Orders}
        customers_sheet_ref: {node: extract_customers, sheetbook: report, sheet: Customers}

  options:
    max_concurrency: 4
    failure_policy: all_fail
```

说明:

- `write_to.sheetbook_sheet` 为 authoring surface 简写；编译后 MUST 解糖为显式的 write nodes 参与 DAG 调度与确定性顺序控制。
- `build_summary.demand.yaml` 通过内置 loader `scalim.dsl.by_yaml.runtime.workflow_loaders:sheetbook_sheet_rows` 消费 `orders_sheet_ref`/`customers_sheet_ref`（ref 结构在本 change 中定稿）。

### Anti-example (should fail-fast): two demands write the same xlsx path

```yaml
workflow:
  runs:
    - id: a
      demand: ./a.demand.yaml # a 的输出写入 ./out/report.xlsx
    - id: b
      demand: ./b.demand.yaml # b 的输出也写入 ./out/report.xlsx
  options:
    max_concurrency: 2
```

期望行为: workflow 在“写入发生前”fail-fast，提示冲突路径与冲突 nodes；推荐迁移为 `sheetbook` + `export_xlsx` + write nodes 或共享 workbook 资源。

## Capabilities

### New Capabilities
- `workflow-sheetbook-resources`: workflow-level sheetbook（内存工作簿）资源，支持跨 nodes 共享写入/读取，并可确定性导出为 xlsx，包含预算/生命周期/可观测性与冲突预检契约

### Modified Capabilities
<!-- 无：本变更以新增 capability spec 的方式承载新增语义；与现有已实现 spec 的差异由后续 sync/spec 演进收敛 -->

## Impact

- Runtime/code:
  - workflow runtime 需要新增 sheetbook resource manager，并与 DAG 调度/确定性写入/观测事件对齐
  - 需要提供内置 loader 访问 workflow artifacts/resources（依赖闭包校验）
  - 可能复用/扩展现有 `ExcelWorkbookSink`（xlsx 导出）与 `run_multi_root_workbook`（多 demand 写 workbook 的既有路径）

- YAML authoring:
  - workflow YAML 将新增 `resources.sheetbooks`（含 `export_xlsx` 导出配置）与对应的 write intent 简写
  - demand YAML 维持稳定：优先通过 workflow 注入 sink/loader 连接 sheetbook，而非在 demand 层新增“workflow 专用语法”

- Docs/spec governance:
  - SSOT:
    - workflow schema DSL 与 hover 文案: `src/scalim/dsl/by_yaml/schema_dsl/**`
    - 规范：`openspec/specs/**/spec.md` 与 changes 的 delta specs（实现阶段通过 sync 合入）
  - Generated（禁止手改）：
    - `src/scalim/dsl/by_yaml/schema/workflow.gen.json`（通过 `just gen-yaml-dsl-schema` 生成）
    - docs 中的 `.gen.` 与 injected blocks（通过 `just gen-docs` 生成）
  - Gates:
    - `just qa`
    - `just openspec-check`
