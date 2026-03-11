> Status (2026-03-11): 已实现(v1 IR/Python-only).当前实现覆盖 workbook 多 sheet、输出组合(router)、派生汇总(group_by + 内置聚合 + finalize 排名)、meta/audit 与 multi-root workbook;待 `just qa`/`just gen` 验收后归档。

## Why

当前运行只能产出单一输出(通常是详情表),无法在同一次运行内生成分析/汇总表,导致详情与分析需要二次离线处理,也无法在同一报表包中稳定交付“明细 + 结论”。对于多 sheet workbook 或“宽表先产出,再按维度汇总”的报表链路,这会长期把编排逻辑卡在 Python 外围。

现在需要把“多输出组合”和“派生输出”作为执行层的一等能力收口进来,先打通一次运行内的详情/汇总协同与同容器多逻辑输出。

## Downstream Survey Highlights (Why Now)

需求侧（以 ET 迁移为主）的现实形态高度集中在以下几类：

- 同一份**明细宽表**拆成多张 sheet（同源分发）。
- “**明细 + 汇总**”两/三张 sheet 的组合交付（先产出事实流，再按维度聚合）。
- 每张 sheet 来自**独立数据源/独立 SQL**（多根数据源 workbook）。
- 现有实现常见“全量 rows 攒内存再写 Excel”的模式，且对 sheet 名冲突/输出顺序/可对拍 meta 支持不足。

因此 add-derived-outputs 在本质上需要覆盖两件事：

- **Workbook 容器 + 多 sheet 输出**（流式写、命名冲突 fail-fast、顺序稳定）
- **同源明细流的多路分发 + 派生汇总**（tee/router + 增量聚合/收尾输出）

## What Changes

- 引入“多输出组合”能力: 单次运行可定义多个输出目标(详情+汇总),可写入同一容器(如同一 workbook 的多 sheet)或独立输出。
- 引入“派生输出”能力: 允许在同一次运行中对详情流做增量聚合并产出汇总表,支持批次累计、收尾输出与二阶段兜底模式。
- v1 明确限定为 IR/Python 配置入口,不在本 change 的 v1 实现中扩展 YAML DSL authoring surface。
- 为了后续 review 能落到“可写的 YAML”形态,本文档补充了若干 YAML DSL 候选方案(仅提案/对齐材料,不代表会在本 change 的 v1 一并实现)。
- 明确同容器命名冲突、输出失败策略、资源控制与并发一致性约束。

## Capabilities

### New Capabilities
- `output-composition`: 单次运行支持多个输出目标、同容器多逻辑输出与容器内命名冲突管理。
- `derived-outputs`: 单次运行支持基于详情流的派生输出、增量聚合与后置聚合兜底路径。

### Modified Capabilities
- None.

## Impact

- 影响执行流程、输出组合层、容器型 sink、派生聚合状态管理与可观测事件对齐。
- 主要风险是内存增长、输出顺序稳定性、以及 `adaptive` 并发下的聚合一致性约束。
- v1 不改 YAML DSL / schema / editor;如需 YAML authoring surface,应作为后续独立 change 处理。

## Compatibility Notes

- thread/process 批次级并行将被移除,执行并发语义收敛为 `seq|adaptive`;本 change 中关于“并行模式下可重复性”的讨论应以 `adaptive` 的批次内并发与提交点回放为主要并发形态。

## Current Code Reality (2026-03-11)

> 本节用于把“候选 DSL 方案”锚定到当前代码边界,避免在 YAML 层做不可能映射的空转讨论。

- 执行请求目前是“单输出”模型: `ExecutionRequest` 只有一个 `OutputSpec` 和一个 `ExportLayout`。(`src/scalim/execution/run_ir.py`)
- 目前仅支持“文件输出 + 一个自定义 sink”的双路 tee,并且要求两端 sink 都是 `IRowSink` 或都为 `IColumnSink`。(`src/scalim/execution/run_ir.py::_create_output_plan`)
- Excel sink 目前是“单 workbook + 单 sheet”: `ExcelSink/ColumnExcelSink` 只接收 `sheet_name` 且各自独立保存文件,没有多 sheet 复用的 workbook 容器。(`src/scalim/sinks/sink_excel.py`)
- 行式输出时,写出发生在 `RowEmissionCoordinator._write_row` 组装 `target_fields` 后;写完会按需释放 batch context 中非 retained 的字段。
  这意味着“派生汇总”若作为 `IRowSink` 形态接在输出链路上,默认只能看见已导出的字段子集。(`src/scalim/execution/pipeline/base/_row_emission.py`)

## YAML DSL Authoring Options (Draft)

> 注意: 以下均为“候选写法”,当前 schema 并不支持。每个方案都需要配套:
> - workbook 容器 sink(Excel 多 sheet 复用)
> - 多输出组合器(router/tee/collector)
> - 派生聚合接口 + 失败策略 + `adaptive` 一致性边界

### Option 0: 保持 YAML 不变,仅 IR/Python 入口组合输出 (v1 baseline)

**YAML(保持现状)**:
```yaml
name: order_detail
main_source: {source_id: orders, loader: "...", params: {...}}
sources: {...}
fields: {...}
output:
  format: csv
  path: ./.tmp/output/detail.csv
  fields:
    - {field_id: order_id}
    - {field_id: supplier_id}
    - {field_id: amount}
    - {field_id: profit}
```

**驱动侧(概念)**: Python/IR 侧把“明细文件 sink”与“派生聚合 sink”挂到同一次 run。

优点:
- 不引入 YAML authoring surface 复杂度;可以先把执行层能力做稳。
- 不改现有 schema,不影响 LSP/editor,迁移成本最低。

缺点:
- ET 迁移场景仍需要 Python 外围编排,无法用单 YAML 表达“报表包(明细+汇总+meta)”。
- workbook 多 sheet 仍需要额外容器实现与 driver 组装,对非 Python 用户不友好。

未来规划:
- 以本 change 的执行层实现为前置,再从 Option 1/2/3 中选择一个 YAML authoring surface 做独立 change(或作为本 change 的 v2)。

### Option 1: 在 demand YAML 内引入 `outputs:` 列表(通用;csv/excel 都可)

核心想法:
- 保留现有 `output:` 作为单输出简写。
- 新增 `outputs:` 时,一个 demand 可以声明多个输出目标;同一 workbook 路径可被推断为同一容器(或显式 `container`).

**示例: 同源明细拆分两张 sheet + 同源汇总 sheet(概念)**:
```yaml
name: order_report
main_source: {source_id: orders, loader: "...", params: {...}}
sources: {...}
fields: {...}

outputs:
  - id: detail
    format: excel
    path: ./.tmp/output/report.xlsx
    excel: {sheet_name: 明细}
    streaming: true
    fields:
      - {field_id: order_id}
      - {field_id: supplier_id}
      - {field_id: amount}
      - {field_id: profit}

  - id: detail_quick
    kind: filtered_detail
    derive:
      from: detail
      where:
        call_by: "myapp.filters:should_quick"  # 概念: 复用 YAML DSL 的 allowlist/安全引用机制,避免引入任意表达式语言
    format: excel
    path: ./.tmp/output/report.xlsx
    excel: {sheet_name: 快付-应走}
    streaming: true
    fields:
      - {field_id: order_id}
      - {field_id: supplier_id}

  - id: summary_by_supplier
    kind: summary
    derive:
      from: detail
      aggregate:
        group_by: [supplier_id]
        metrics:
          order_cnt: {op: count, field_id: order_id}
          sum_amount: {op: sum, field_id: amount}
          sum_profit: {op: sum, field_id: profit}
    format: excel
    path: ./.tmp/output/report.xlsx
    excel: {sheet_name: 供应商汇总}
    streaming: false  # finalize 写出
    fields:
      - {field_id: supplier_id}
      - {field_id: order_cnt}
      - {field_id: sum_amount}
      - {field_id: sum_profit}
```

优点:
- 与现有 `output` 配置形态最接近,可复用大部分字段/覆盖语义与 `overrides.output.*` 心智模型。
- 天然支持“多个独立文件输出”(csv/csv 或 csv+excel)与“同 workbook 多 sheet”(通过容器推断或显式声明)。

缺点:
- 需要引入 format 专属参数(例如 `excel.sheet_name`),schema 复杂度上升。
- `derive.where/aggregate` 会把 YAML DSL 从“宽表编译”扩展为“轻量数据流变换语言”,需要严格的安全/可验证子集与清晰的能力边界。
- 受当前写出点限制,派生汇总如果挂在行式输出链路上,只能看到导出字段;因此 `derive` 必须声明所需字段并驱动 retained/target 选择,否则会出现“汇总缺字段”的隐性错误。

未来规划:
- v2 先落地 `outputs` 但只支持“不改变行形状”的分发(多 sheet detail / filtered_detail / audit),不引入聚合。
- v3 再引入 `derive.aggregate` 的最小可增量指标集合(count/sum/min/max/count_true)与 finalize 约束;Rank/排序走 finalize 或二阶段兜底。

### Option 2: Excel-first: `output.format=excel` 时支持 `output.workbook.sheets`(更贴近报表心智)

核心想法:
- 仍然是“一个 demand 产出一个 workbook 容器”,把 sheet 当作一等配置项。
- sheet 内允许 `select`(字段子集)、`where`(过滤)与 `aggregate`(派生汇总)等能力;非 excel 输出仍使用原 `output`。

**示例: 一个 workbook 多 sheet(概念)**:
```yaml
name: order_report
main_source: {source_id: orders, loader: "...", params: {...}}
sources: {...}
fields: {...}

output:
  format: excel
  path: ./.tmp/output/report.xlsx
  workbook:
    name_conflict: fail_fast
    sheet_order: [明细, 供应商汇总, 运行参数]
    sheets:
      明细:
        kind: detail
        streaming: true
        select: [order_id, supplier_id, amount, profit]

      供应商汇总:
        kind: summary
        streaming: false
        from: 明细
        aggregate:
          group_by: [supplier_id]
          metrics:
            order_cnt: {op: count, field_id: order_id}
            sum_amount: {op: sum, field_id: amount}
            sum_profit: {op: sum, field_id: profit}

      运行参数:
        kind: meta
        rows:
          - [run_name, "$runtime.run_name"]  # 概念: 由 driver 通过 runtime_vars 注入
          - [start_datetime, "$runtime.start_datetime"]
```

优点:
- 对“多 sheet workbook”场景表达最自然,避免在每个输出条目里重复 `format/path`。
- 容器级策略(命名冲突/排序/默认 streaming)更容易集中管理。

缺点:
- Excel 专用,对“多个 csv 输出文件”的场景不直观(仍需另开 `outputs` 或额外语法)。
- 仍然会遇到派生汇总所需字段的声明与 retained/targets 协调问题;如果 `select` 过早裁剪字段,会影响后续 `aggregate`。

未来规划:
- v2 仅支持 `workbook.sheets.<name>.select`(同源拆分)与基础 meta sheet,不引入 `aggregate`。
- v3 把 `aggregate` 作为显式开关能力逐步加入,并要求 sheet 声明 `requires_fields`(或系统自动从 `aggregate` 推导)以避免隐性缺字段。

### Option 3: 引入“报表包 YAML”(bundle)作为新 DSL 文件类型,引用多个 demand YAML (支持 MultiRootSheets)

核心想法:
- 不在 `demand` schema 上堆更多概念;新增一种顶层 YAML(例如 `report_bundle.yaml`),用于声明 container 与 sheets/datasets。
- 每个 dataset 引用一个现有 demand YAML,并可对其 `output` 做 overrides(例如禁用文件输出,改为只产生内存 sink)。

**示例: workbook 里既有同源派生 sheet,也有独立 demand sheet(概念)**:
```yaml
kind: report_bundle
container:
  type: workbook
  path: ./.tmp/output/report.xlsx
  name_conflict: fail_fast

datasets:
  detail:
    demand: ./order_detail.demand.yaml
    overrides:
      output: {path: null}  # 禁用该 demand 的单文件输出,把 rows 交给 bundle 统一写入

  channel:
    demand: ./channel_view.demand.yaml
    overrides:
      output: {path: null}

sheets:
  - name: 明细
    from: detail
    select: [order_id, supplier_id, amount, profit]

  - name: 供应商汇总
    from: detail
    aggregate:
      group_by: [supplier_id]
      metrics:
        order_cnt: {op: count, field_id: order_id}
        sum_amount: {op: sum, field_id: amount}

  - name: 渠道
    from: channel
    select: [channel_id, channel_name, paid_order_cnt]
```

优点:
- 最小化对现有 demand DSL 的侵入;demand 仍然保持“一个宽表需求”的边界与校验习惯。
- 自然支持 MultiRootSheets(多根数据源 workbook)与复用既有 demand YAML。

缺点:
- 需要新增一套编译/运行入口与 schema/LSP 支持,工程量不小。
- dataset 之间的缓存共享与单次运行一致性需要额外设计;否则容易退化为“多次 run 打包”为主,与本 change 的“单次 run”目标存在张力。

未来规划:
- 先把 bundle 做成“编排层”并明确语义: 默认多 demand 顺序执行并写入同一 workbook,只保证容器级顺序与命名策略。
- 待执行层 multi-root/共享缓存能力成熟后,再把 bundle 编译成单 ExecutionPlan(或部分共享 loader cache)以提升性能。

## Cross-Cutting Policy Questions (To Resolve in Review)

- 命名冲突策略: workbook/sheet/output id 重名时默认 `fail_fast`;是否允许 `auto_rename` 仅用于 dev?
- 失败策略(failure policy): 多输出场景下,是“任一输出失败即整次 run 失败”,还是允许 best-effort 并产出 partial artifact + audit/meta?
- 顺序稳定性: 输出/写入顺序必须可控且稳定(用于对拍);默认由 `outputs` 列表顺序或 `sheet_order` 明确指定。
- `adaptive` 一致性: 派生聚合的默认约束应写死(例如仅允许交换律/结合律聚合,或强制在 finalize 单线程执行),避免非确定统计。
- 字段可见性: 派生汇总需要的字段如何声明/推导,以及是否允许“保留但不导出”的 retained 字段集合。

## Roadmap (Suggested)

为了避免 YAML 过早绑定实现细节,建议按阶段推进:

1) v1(本 change 的实现阶段): IR/Python-only 输出组合 + workbook 容器 sink + 基础派生聚合接口(最小可用)。
2) v2(YAML authoring surface): 在 Option 1 与 Option 2 之间选择一个作为“单 demand 多输出”入口,先覆盖同源分发与 workbook 多 sheet。
3) v3(派生聚合 YAML 化): 增量聚合指标集合 + finalize 约束 + failure policy 默认值 + `adaptive` 并发一致性边界。
4) v4(MultiRootSheets): 采用 Option 3 的 bundle DSL,或在 demand DSL 内引入 multi-root(成本更高),并补全迁移文档与 editor 支持。

## Documentation & Migration (When YAML Is Enabled)

- 需要为新增配置键补齐字段级 `md` 注释与 examples(参照现有 `OutputConfig` 的注释密度),确保 schema/LSP 体验可用。
- 若对现有 YAML 有 breaking(例如从 `output` 迁移到 `outputs`),需要在 `docs/doc/yaml-dsl/upgrades/` 增加升级文档并接入自动索引(`just gen`)。
