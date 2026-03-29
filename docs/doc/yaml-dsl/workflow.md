# YAML DSL Workflow (编排多 demand)

??? note "适用读者"
    - 需要把“多条 demand + Python glue”收敛为可复用编排入口的使用方
    - 需要统一 runs 粒度并发/失败策略/共享 preload cache 治理的开发者

这页讲 **workflow YAML**(编排文件)的语法,以及对应的 Python 运行入口。workflow YAML 和 demand YAML 是两套配置:

- demand YAML: `name/main_source/sources/relations/fields/...`
- workflow YAML: `workflow.runs/options/resources`(只负责“编排多个 demand”与“声明共享输出资源”)

## 0) 校验与编辑器($schema)配置

workflow YAML 支持两类校验入口:

<!-- BEGIN AUTOGEN:yaml-dsl-workflow-cli-min-commands -->
1) workflow-level full validate(静态/编译期;递归校验引用的 demands;不执行 workflow):

```bash
uv run scalim-cli yaml-dsl validate --type workflow path/to/workflow.yaml
```

2) schema-only 校验(结构/unknown-fields;依赖 `workflow.gen.json`):

```bash
uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json path/to/workflow.yaml
```

本地编辑时,推荐直接批量写入 schema modeline(同 demand YAML 的做法一致,只是在 `--type` 上改为 `workflow`):

- 批量写入/更新 `$schema` 头部(默认同时写 Red Hat + JetBrains 两种 modeline; 用 `--comment-style` 控制): `uv run scalim-cli yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`

```yaml
# yaml-language-server: $schema=.../workflow.gen.json
# $schema: .../workflow.gen.json
```
<!-- END AUTOGEN:yaml-dsl-workflow-cli-min-commands -->

说明:

- `yaml-dsl validate` 默认 `--type auto`: 根据 YAML 顶层结构推断 demand/workflow;CI/脚本建议显式写 `--type workflow`
- 若 `workflow.runs[*].demand` 使用 alias 语法,可用 `--path-alias <alias>=<path>` 注入解析(可重复)

## 1) 最小结构

```yaml
# yaml-language-server: $schema=.../workflow.gen.json
# $schema: .../workflow.gen.json

workflow:
  runs:
    - id: orders
      demand: ./orders_report.yaml
    - id: customers
      demand: ./customers_report.yaml
  options:
    max_concurrency: 2
    failure_policy: primary_only
    cache_pool:
      conflict_policy: error
      release_policy: dag_refcount
      budget:
        max_entries: 16
        over_budget_policy: fail_fast
```

语义约束(启动前 fail-fast):

- `workflow.runs` 必须非空
- `workflow.runs[*].id` 必须非空且全局唯一
- `workflow.runs[*].demand` 必须为非空字符串
- `workflow.options.max_concurrency` 必须为整数且 >= 1(默认 `1`)
- `workflow.options.failure_policy` 为 `all_fail` 或 `primary_only`(默认 `all_fail`)
- `workflow.options.cache_pool` MAY 缺省(表示不启用 workflow-scope cache pool)
  - 当存在时,其 `conflict_policy/release_policy/budget` 为必填
  - `budget.max_entries` 必须为整数且 >= 1

## 2) demand 路径解析与 `path_aliases`

`run.demand` 路径解析规则:

- 相对路径以 workflow 文件所在目录为基准
- 支持通过 CLI `--path-alias <alias>=<path>` 或 Python 入口注入 `path_aliases` 来解析:
  - `"@/x/y.yaml"` (alias 为 `"@"`)
  - `"ALIAS:/x/y.yaml"` (alias 为 `"ALIAS"`)

## 3) `depends_on` + `init_vars`: DAG 与上下文注入

`workflow.runs[*].depends_on` 用于声明 runs 间的 **显式 DAG 依赖**(按 run id 引用):

```yaml
workflow:
  runs:
    - id: extract_orders
      demand: ./extract_orders.yaml
    - id: agg_orders
      demand: ./agg_orders.yaml
      depends_on: [extract_orders]
```

- 语义约束(启动前 fail-fast):
  - deps 引用的 run id 必须存在
  - 必须无环(有 cycle 会报出可读的环路径)

`workflow.runs[*].init_vars` 用于为该 run 对应的 demand 注入 init vars(在 demand 编译期可通过 `{$init_var: ...}` 引用).

当 run 依赖上游时,`init_vars` 里允许使用 `$ctx` 指令读取上游 ctx(详见下一节),写法为 **对象节点**(不是字符串插值):

```yaml
workflow:
  runs:
    - id: a
      demand: ./a.yaml
    - id: b
      demand: ./b.yaml
      depends_on: [a]
      init_vars:
        a_output_path: {$ctx: {node: a, key: output_path}}
```

## 3.1) `main_rows_from`: 上游内存 rows → 下游 `main_rows`

当 workflow 内部需要把上游 run 的结果作为下游 run 的主行流输入(不落盘/不字符串化)时,可以使用:

- `workflow.runs[*].main_rows_from: {run: <producer_run_id>}`

语义:

- consumer MUST 显式 `depends_on` producer(否则启动前 fail-fast)
- producer 仅在被引用时才会启用内存 rows 捕获(避免无意间常驻大对象)
- 下游 demand 执行时会注入 `main_rows` 并绕过 main source loader

```yaml
workflow:
  runs:
    - id: a
      demand: ./a.yaml
    - id: b
      demand: ./b.yaml
      depends_on: [a]
      main_rows_from:
        run: a
```

## 4) `ctx`: workflow-level ctx store（跨节点小体量数据）

workflow 在一次执行中维护 workflow-level ctx store,用于在依赖边上传递小体量 JSON-like 数据.

- ctx 以 `workflow_node_id` 为命名空间(对 demand 节点即 `runs[*].id`)
- ctx 只能在 **依赖闭包**内读取(没有声明依赖的节点不能读上游)
- 系统禁止把 rows/dataset/大型输出塞进 ctx; 大对象必须走 artifacts/resources 路径
- 护栏可通过 `workflow.options.ctx` 配置:

```yaml
workflow:
  options:
    ctx:
      max_value_bytes: 65536
      max_bytes: 1048576
```

需求节点完成时会发布一组稳定的默认 ctx keys(用于减少 Python glue):

- `output_path`(string|null)
- `total_rows`(int|null)
- `duration_secs`(float; seconds)

## 5) `cache_pool`: workflow-scope cache pool

当 `workflow.options.cache_pool` 存在时:

- 系统会在同一次 workflow 执行内提供 workflow-scope cache pool,用于承载可共享的缓存条目(v0: `cache_mode: preload_forever` 的预加载结果)
- cache pool 以“可复现的 signature”作为 key,避免复用错误数据;signature 至少包含:
  - 缓存条目 kind(例如 `preload_forever`)
  - `source_id`
  - loader 引用
  - **已渲染的 params**(含已解析的 `{$init_var: ...}` / 未来的 `{$ctx: ...}`)
  - normalize/key/lookup_cast 等会影响结果形状的关键字段
- 冲突策略 `cache_pool.conflict_policy`:
  - `error`: 当同一逻辑 key(同 kind+source_id)出现多个不同 signature 时 fail-fast
  - `separate|warn`: 允许并行存在多个 entries(互不复用),并发出可观测告警(含差异摘要)
- 生命周期 `cache_pool.release_policy`:
  - `dag_refcount`: 基于 workflow IR 推导 consumer set 上界,并在最后一个消费者完成后释放/可淘汰
  - `workflow_end`: 禁止按 refcount 自动释放,仅在 workflow 结束时统一清理
- `cache_pool.pin`:
  - 可选 escape hatch: 强制指定条目常驻到 workflow 结束(v0 仅支持 kind=preload_forever + source_id)
- 预算 `cache_pool.budget`:
  - `max_entries`: entries 数量上限(v0)
  - `over_budget_policy`: `fail_fast|evict_lru`(仅淘汰 refcount=0 且未被 `cache_pool.pin` 固定的条目;否则 fail-fast)
- 可观测性: 系统会发出 `workflow_cache_acquire/release/evict` 事件,并复用 `workflow_exec_id/workflow_node_id` 归因字段

迁移:

- `workflow.options.share_preload_cache` 已移除,请改用 `workflow.options.cache_pool`

## 6) `resources` + `writes`: 声明共享输出资源并写入

workflow YAML 支持在 workflow scope 声明共享输出资源,并通过 run 的 `writes` 列表声明 0..N 条写入意图:

- `workflow.resources.workbooks.<id>.path`: 共享 workbook 输出路径
- `workflow.resources.csvs.<id>.path`: 共享 csv 输出路径
- `workflow.resources.sheetbooks.<id>`: 共享 sheetbook 资源(内存工作簿) + 可选 `export_xlsx`
  - `budget.max_sheets/max_total_cells` 为必填护栏
  - `export_xlsx.path` 可选,用于 workflow 结束时导出为最终 xlsx

`runs[*].writes` 为写入意图数组(缺省/空数组表示无写入意图),每个 item MUST 恰好包含一个 intent key:

- `workbook_sheet` / `workbook_append`
- `csv_append`
- `sheetbook_sheet` / `sheetbook_append`

示例: 同一个 run 产出两个 outputs,并通过两条 `writes` 写入同一个 sheetbook 的不同 sheet,在末尾导出:

```yaml
workflow:
  resources:
    sheetbooks:
      report:
        budget:
          max_sheets: 16
          max_total_cells: 2000000
        export_xlsx:
          path: ./out/report.xlsx
          write_lock: true
  runs:
    - id: main
      demand: ./main.yaml
      writes:
        - sheetbook_sheet:
            sheetbook: report
            sheet: Metrics
            output: metrics
            on_conflict: error
        - sheetbook_sheet:
            sheetbook: report
            sheet: Detail
            output: detail
            on_conflict: error
```

注意:

- `writes` 目前只支持消费 CSV outputs: `writes[*].*.output` 指向的 demand output 需要生成 `.csv` 文件(通常在上游 demand 用 `outputs.*.container.type: csv`). workbook 输出暂不支持直接作为 write node 输入.
- 写入顺序 SSOT: 以 `workflow.runs` 声明顺序为一级,以 `writes` 声明顺序为二级(同一共享资源互斥串行,不依赖并发完成时序),以保证确定性
- 当存在潜在的输出路径冲突(多个 nodes 写同一路径)时,系统会在写入发生前 fail-fast

迁移:

- `runs[*].write_to` 已移除,请改用 `writes: [{<kind>: <cfg>}]`；旧写法会 fail-fast 并给出可复制的迁移提示

## 7) Python 运行入口

当前暂不扩展 workflow runner CLI; 先用 Python 入口:

```python
from scalim.dsl.by_yaml import run_workflow

result = run_workflow(
    "path/to/workflow.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
    path_aliases={"@": "/abs/project_root"},
)

for outcome in result.outcomes:
    if outcome.error is not None:
        print("FAILED:", outcome.run_id, outcome.error.message)
    else:
        print("OK:", outcome.run_id, outcome.result.total_rows)
```

失败策略:

- `all_fail`: 任一 run 失败会抛出异常(包装为 `WorkflowRunFailedError`,并通过 `__cause__` 关联原异常)
- `primary_only`: workflow 继续执行,返回值 `outcomes` 中包含成功/失败的可检查结构

并发契约:

- 当 `max_concurrency>1` 且提供了 `components`(hooks/observers)时,系统会在并发执行阶段 capture 事件,并在 workflow 结束后以单线程按稳定顺序 replay 给 components(仍满足 `no-external-callback-under-lock`)
  - components 默认不要求线程安全(同一时刻最多一个回调在执行)
  - 代价: 并发模式下 components 的回调可能非实时(在 replay 阶段触发)
- 如需严格实时回调,请将 `max_concurrency` 设为 `1`
