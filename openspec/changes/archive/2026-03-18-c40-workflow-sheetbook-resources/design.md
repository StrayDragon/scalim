## Context

当前系统在 **demand** 层已经具备 Excel workbook 的多 sheet 输出能力：

- `ExcelWorkbookSink` 在内存中维护一个 `openpyxl` `write_only` workbook
- 多 sheet 通过 `create_sheet_row_sink()` 共享同一 workbook
- 在 `close()` 时一次性保存并原子替换目标路径
- 可选 `write_lock` 通过 `.scalim.lock` 文件 fail-fast 防止并发写同一路径

此外已有一个 Python 入口 `run_multi_root_workbook(...)` 可以将多个独立 demand 顺序写入同一 workbook（容器复用，保证 sheet 顺序），但它是 Python glue/特例，并不具备 workflow-level 的 DAG/资源/可观测性/生命周期治理能力。

随着 workflow 演进到 DAG、共享输出容器与写出节点（以及未来的 artifacts/resources 生命周期治理），我们遇到两个缺口：

1) **跨 nodes 共享 workbook 的中间表示**：现有 `ExcelWorkbookSink(write_only)` 适合“最终落盘”，但不适合“作为输入再次被读取/加工”。

2) **输出路径冲突的确定性诊断**：当多个并发 nodes 的 demand 都写同一个 xlsx 路径时，当前只能在运行时依赖写锁 fail-fast；错误时机晚、诊断粒度有限且对用户不友好。更糟的是：在未启用 write_lock 时可能产生非确定性损坏风险。

约束/对齐：

- `ctx` 仅承载 JSON-like 小对象；workbook 这种大对象必须走 artifacts/resources
- workflow 已确立“结构编译 + 物化编译（compile-on-ready）”边界；本变更应以此为基础
- 必须保持 Python 3.6 兼容，并遵循既有 docs/生成物治理与 `just openspec-check` 门禁

## Goals / Non-Goals

**Goals:**

- 引入 workflow-level `sheetbook`（内存工作簿）资源：可跨 nodes 共享写入，并可作为下游输入读取
- 支持将 sheetbook **确定性导出** 为最终 xlsx：延迟导出、原子落盘、失败默认 discard
- 在 workflow 编译/校验阶段对 Excel 输出路径冲突做 fail-fast 预检，避免运行时写锁不确定失败
- 与 `workflow-observability-bridge` 对齐：sheetbook 生命周期事件可 join 回 DAG
- 与 cache pool/lifecycle 方向对齐：sheetbook 具备预算护栏与释放策略（至少 fail-fast）

**Non-Goals:**

- 不将 sheetbook 放入 `ctx`（禁止绕开 artifacts/resources 边界）
- 不支持跨进程/分布式共享（sheetbook 仅限单次 workflow 调用内）
- 不在本 change 内提供“任意 xlsx 文件读取为 sheetbook”的通用导入能力（可作为后续扩展）

## Decisions

### 1) Sheetbook 的定位：资源（resource）而非 ctx / 临时文件

sheetbook 是 workflow-level resource：

- 生命周期由 workflow runtime 管理（create/hold/export/discard/release）
- 可被多个 nodes 写入（互斥/串行，确定性顺序）
- 可被下游 nodes 读取（作为输入），且受 deps 可见性约束

不使用“中间落盘 xlsx 再读取”作为默认路径，原因：

- IO 成本高且难以治理（临时文件清理、失败语义）
- 对拍/确定性难以保证（外部环境差异）
- 读写互斥与诊断会变复杂

### 2) 数据表示：面向表格的可读结构，而非 `write_only` workbook

`ExcelWorkbookSink(write_only)` 的优点是流式写入与低内存，但它不可读。

因此 sheetbook 的内部表示应满足：

- 可读：下游可按 sheet 获取 rows（用于内置 loader）
- 可追加：支持 append/write 的确定性合并语义
- 可导出：能够稳定导出到 xlsx（复用既有 Excel 写出能力）

实现可选方案：

- 方案 A（推荐 MVP）：sheet -> `InMemoryColumnSink`（列式内存表示，适合宽表）
- 方案 B：sheet -> `InMemoryRowSink`（实现简单，但宽表内存不友好）

### 3) 写入模型：沿用 workflow 的写出节点语义

sheetbook 的写入与 `workflow-shared-output-containers` 的写出节点保持一致的心智模型：

- `write_sheet`：写入/覆盖某个 sheet（策略可配置）
- `append_sheet`：追加写入某个 sheet（字段对齐与 header 策略显式、可测试）

即使 YAML authoring surface 选择提供简写，编译后语义仍应解糖为显式 write nodes，以复用确定性调度、资源互斥与观测。

### 4) 导出语义：资源 commit 阶段导出 + 原子落盘

sheetbook 到 xlsx 的导出属于“最终输出提交”：

- 通过 `resources.sheetbooks[*].export_xlsx` 声明导出目标；在 workflow 成功结束时统一 commit 导出（失败默认 discard）
- 导出使用临时文件 + 原子替换（与现有 excel sinks 对齐）
- 若启用 write_lock，导出阶段使用写锁，防止外部并发写

### 5) Excel 输出冲突：从运行时写锁转为“写入前”fail-fast

在 workflow 场景下，我们希望用户在启动前就得到清晰错误：

- 对于“多个 nodes 直接写同一个 xlsx 路径”的情况：
  - 若路径可在结构编译阶段静态提取,则结构编译阶段 fail-fast
  - 若路径依赖 `init_vars/$ctx` 等动态渲染,则在 node 物化编译后、实际写入前 fail-fast
- 对于“workflow 声明共享 workbook/sheetbook 资源”的情况：禁止 nodes 直接写该路径，必须通过共享资源 + 写出节点

这既避免了不确定的运行时 lock 竞争，也避免未加锁时的数据损坏风险。

### 6) 读取模型：内置 loader + deps 可见性

为了让 sheetbook 可作为输入：

- 提供内置 loader `scalim.dsl.by_yaml.runtime.workflow_loaders:sheetbook_sheet_rows` 按 `<node_id, sheet_name>` 读取 rows
- 该 loader 通过 workflow runner 提供的运行时上下文访问 sheetbook（实现形态 SSOT: runner 在执行 node 时设置 thread-local workflow context）
- 强制 deps 可见性：只能读取依赖闭包内 nodes 的 sheetbook
- 错误要可诊断：不存在的 sheet、越界引用都必须 fail-fast 并给出摘要

## Examples

### 1) Shared sheetbook as intermediate + export to xlsx

```yaml
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

    # sheetbook 的导出在 workflow 成功结束时由资源管理器统一 commit（原子落盘）
```

说明：

- `write_to.sheetbook_sheet` 作为 authoring surface 的简写存在即可，但编译后 MUST 解糖为显式 write nodes（以便参与确定性顺序控制与观测事件归因）。
- export 采用临时文件 + 原子替换；失败默认 discard，避免留下“已提交但不完整”的最终文件。

### 2) Downstream demand consumes sheetbook rows (built-in loader)

workflow 侧把引用注入为 `init_vars`，避免把 workflow node id / sheet 名硬编码进 demand YAML：

```yaml
workflow:
  runs:
    - id: build_summary
      demand: ./build_summary.demand.yaml
      depends_on: [extract_orders]
      init_vars:
        orders_sheet_ref: {node: extract_orders, sheetbook: report, sheet: Orders}
```

`build_summary.demand.yaml`（示意）：

```yaml
main_source:
  loader: "scalim.dsl.by_yaml.runtime.workflow_loaders:sheetbook_sheet_rows"
  params:
    ref: {$init_var: orders_sheet_ref}
  key: order_id
```

关键约束：

- 该内置 loader MUST 受 deps 可见性约束：只能读取依赖闭包内上游 nodes 的 sheetbook/sheet。
- sheetbook/rows 属于资源/工件，不进入 `ctx`；ctx 只承载小摘要（路径/计数/耗时等）。

### 3) Anti-example: direct xlsx output-path collision in workflow

```yaml
workflow:
  runs:
    - id: a
      demand: ./a.demand.yaml # 输出写 ./out/report.xlsx
    - id: b
      demand: ./b.demand.yaml # 也输出写 ./out/report.xlsx
```

期望行为：
- 若冲突路径可在结构编译阶段静态提取,则结构编译阶段直接 fail-fast
- 若路径依赖 `init_vars/$ctx` 等动态渲染,则在 node 物化编译后、实际写入前 fail-fast（仍保证确定性与可诊断）

## Risks / Trade-offs

- [内存占用风险] sheetbook 可能很大 → 预算护栏（max_sheets/max_total_cells）+ fail-fast；后续可与 cache pool 预算/淘汰结合
- [写入确定性 vs 吞吐] 串行化写入会降低并发 → 仅对同一 sheetbook 互斥；不同资源可并行；优先保证确定性/正确性
- [读取语义复杂] 将 workbook 作为输入会引入更多边界 → MVP 仅支持“读取 sheet rows”，不支持随机访问/公式依赖

## Migration Plan

- 新增能力默认不影响不使用 sheetbook 的 workflow
- 对于现有 workflow 中“多 nodes 直接写同一路径”的用法：迁移为共享 workbook/sheetbook 资源 + 写出节点；不再依赖运行时写锁竞争

## Final Decisions (no open questions)

- 预算配置入口固定为 `workflow.resources.sheetbooks.<id>.budget`:
  - v0 SSOT: `max_sheets` / `max_total_cells`
  - 超限行为: fail-fast（错误必须包含当前计数与上限摘要）
- append/merge 默认策略与 `workflow-shared-output-containers` 对齐:
  - 字段对齐默认按 `field_id`
  - header 默认仅输出一次
  - 冲突默认 fail-fast
- 不支持从 xlsx 导入 sheetbook:
  - “写文件 → 再读文件”的混合流程不在本 change 内落地（避免引入 IO/清理/确定性边界）

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
