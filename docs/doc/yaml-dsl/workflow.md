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
uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/yaml_dsl/schema/workflow.gen.json path/to/workflow.yaml
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
- `workflow.options.resources_wait` 与 `workflow.options.output_staging` 已迁出 workflow YAML(运行期策略边界);请通过 runtime entrypoints 配置:
  - `run_workflow(..., workflow_resources_wait=..., workflow_output_staging=...)`
- `workflow.options.cache_pool` MAY 缺省(表示不启用 workflow-scope cache pool)
  - 当存在时,其 `conflict_policy/release_policy/budget` 为必填
  - `budget.max_entries` 必须为整数且 >= 1

### 1.1) `workflow_resources_wait`: 共享资源 join/wait 超时与诊断(runtime entrypoint)

workflow 的共享输出资源(book/csv/sheetbook)在并发模式下会用 joinable inflight 去重 owner 创建；当 owner 卡死/外部 IO 阻塞时,waiter 可能会被挂起。
为避免生产 hang,workflow 默认对 inflight join/wait 启用超时 fail-fast：

- `max_wait_s` 缺省等价于 `600` 秒
- diagnostics 默认禁用(仅当显式开启时才告警)

注意:

- `workflow.options.resources_wait` 已从 workflow YAML 迁出;若继续在 YAML 中声明会 fail-fast.

示例(Python):

```python
from scalim.dsl.yaml_dsl import RunOptions, run_workflow
from scalim.dsl.yaml_dsl.workflow_types import WorkflowResourcesWaitDiagnosticsOptions, WorkflowResourcesWaitOptions

run_workflow(
    "path/to/workflow.yaml",
    options=RunOptions(allowed_modules=frozenset(["myapp"])),
    workflow_resources_wait=WorkflowResourcesWaitOptions(
        max_wait_s=600.0,
        diagnostics=WorkflowResourcesWaitDiagnosticsOptions(
            enabled=True,
            warn_after_s=30.0,
            repeat_every_s=60.0,
            capture_owner_callsite=True,
        ),
    ),
)
```

### 1.2) `workflow_output_staging`: workflow 输出 staging + 最终发布(runtime entrypoint)

workflow 的共享输出(例如 `workflow.resources.books` 导出的 `.xlsx` / 合并的 `.csv`)默认采用 **staging → publish** 两阶段:

1. commit 阶段先写入 staging 目录(避免在运行中污染最终路径)
2. workflow 成功结束后再覆盖发布到最终导出路径

默认 staging 目录布局:

- `<final_dir>/.scalim-staging/<workflow_exec_id>/<filename>`

清理策略:

- success 默认清理 staging(`keep_on_success=false`)
- failure 默认保留 staging(`keep_on_failure=true`,便于排障)

注意:

- `workflow.options.output_staging` 已从 workflow YAML 迁出;若继续在 YAML 中声明会 fail-fast.

示例(Python):

```python
from scalim.dsl.yaml_dsl import RunOptions, run_workflow
from scalim.dsl.yaml_dsl.workflow_types import WorkflowOutputStagingOptions

run_workflow(
    "path/to/workflow.yaml",
    options=RunOptions(allowed_modules=frozenset(["myapp"])),
    workflow_output_staging=WorkflowOutputStagingOptions(
        dir_name=".scalim-staging",
        keep_on_success=False,
        keep_on_failure=True,
    ),
)
```

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

## 6) `workflow.resources.books`: 共享 book 资源（无 `writes`）

workflow YAML 只负责两件事:

- 编排多条 demand(`workflow.runs/options/ctx/cache_pool`)
- 声明 workflow-scope 的共享 IO 资源: `workflow.resources.books`

当前实现里,workflow **不再**提供显式的“写入意图”字段;共享输出的写入由 demand 的 outputs 绑定表达,并由 workflow 编译期推导写入节点。
共享输出的写入顺序与写入语义由 demand YAML 的 outputs 绑定表达,并由 workflow 编译期推导写入节点(确定性、串行化、可冲突检查):

- book 资源声明: `resources.books.<book_id>`
  - 既可以在 demand YAML 声明(standalone 也能跑),也可以在 workflow YAML 的 `workflow.resources.books` 统一声明/覆盖
  - `kind: xlsx_file|xlsx_memory`
- 输出到 book 的绑定: `outputs[*].to.book` / `outputs[*].to.sheet`
- 写入策略: `resources.books.*.write_defaults`(workbook SSOT) + `outputs[*].write`(仅 output-local header 行为: `include_header` / `header_fields_output_by`)

约定:

- CSV 输出使用 `resources.files.<file_id>` + `outputs[*].to.file`
- Excel 输出使用 `resources.books.<book_id>` + `outputs[*].to.book/to.sheet`

注意:

- workflow YAML **不支持** `imports` / `$import` 片段导入(不做 imports expansion)。
- 若需要复用资源声明,优先使用 YAML anchors(`_templates`)或在 demand YAML 中使用 `$import` 生成最终 `resources.*`,workflow 侧仅做声明/覆盖。

示例: workflow 统一声明一个共享 book(`xlsx_memory`),各 run 的 demand 只负责声明 outputs 绑定:

workflow YAML:

```yaml
workflow:
  resources:
    books:
      report:
        kind: xlsx_memory
        budget:
          max_sheets: 16
          max_total_cells: 2000000
        export_xlsx:
          path: ./out

  runs:
    - id: main
      demand: ./main.yaml
    - id: agg
      demand: ./agg.yaml
      depends_on: [main]
```

main.yaml(示意):

```yaml
outputs:
  - name: detail
    to: {book: report, sheet: 明细}
    fields: [order_id, amount_yuan]
```

## 7) Python 运行入口

当前暂不扩展 workflow runner CLI; 先用 Python 入口:

```python
from scalim.dsl.yaml_dsl import RunOptions, run_workflow

result = run_workflow(
    "path/to/workflow.yaml",
    options=RunOptions(allowed_modules=frozenset(["myapp.loaders"])),
    path_aliases={"@": "/abs/project_root"},
)

for outcome in result.outcomes:
    if outcome.error is not None:
        print("FAILED:", outcome.run_id, outcome.error.message)
    else:
        print("OK:", outcome.run_id, outcome.result.total_rows)
```

### 7.1) `run_options_patches_by_run_id`: per-run runtime policy(按 run id 注入差异化运行策略)

当 workflow DAG 中存在多个 runs 时,真实生产场景往往需要“不同 run 使用不同运行策略”:

- `batch_size`: 有的 run 更适合小批降低内存峰值,有的 run 更适合大批提升吞吐
- `components`: 仅对某个 run 追加调试 observer/hook(不污染整张图)
- `guardrails/loader_retry/overrides`: 对特定 run 单独加强或关闭

使用方式:在 Python 入口 `run_workflow(..., run_options_patches_by_run_id=...)` 中按 `workflow.runs[*].id` 提供 patch:

- key: `workflow.runs[*].id`(字符串)
- value: **typed** 的 `WorkflowRunOptionsPatch`(不支持 dict 形状 patch)
- patch 优先级高于 `run_workflow(..., options=RunOptions(...))` 的全局 knobs
- omission / `UNSET` 表示继承;`None` 在支持的字段上表示显式禁用

示例 1: per-run `batch_size` 覆盖全局默认

```python
from scalim.dsl.yaml_dsl import RunOptions, run_workflow
from scalim.dsl.yaml_dsl.workflow_types import WorkflowRunOptionsPatch

run_workflow(
    "path/to/workflow.yaml",
    options=RunOptions(allowed_modules=frozenset(["myapp.loaders"]), batch_size=2000),  # 全局默认
    run_options_patches_by_run_id={
        "d10_paid_orders": WorkflowRunOptionsPatch(batch_size=5000),  # 仅该 run 用更大 batch
    },
)
```

示例 2: 仅对某个 run 追加一个调试组件(append,保序)

```python
from scalim.dsl.yaml_dsl import RunOptions, run_workflow
from scalim.dsl.yaml_dsl.workflow_types import ComponentsExtend, WorkflowRunOptionsPatch

run_workflow(
    "path/to/workflow.yaml",
    options=RunOptions(allowed_modules=frozenset(["myapp.loaders"]), components=[my_prod_observer]),
    run_options_patches_by_run_id={
        "d70_summary_ranking": WorkflowRunOptionsPatch(
            components=ComponentsExtend([my_debug_observer]),
        ),
    },
)
```

示例 3: 对单个 run 显式禁用全局 `batch_size`(该 run 不分批)

```python
from scalim.dsl.yaml_dsl import RunOptions, run_workflow
from scalim.dsl.yaml_dsl.workflow_types import WorkflowRunOptionsPatch

run_workflow(
    "path/to/workflow.yaml",
    options=RunOptions(allowed_modules=frozenset(["myapp.loaders"]), batch_size=2000),
    run_options_patches_by_run_id={
        "d20_registered_users": WorkflowRunOptionsPatch(batch_size=None),
    },
)
```

常见错误与诊断:

- unknown run id: fail-fast 并列出当前 workflow 的合法 ids
- dict patch payload: `run_options_patches_by_run_id={"A": {"batch_size": 5000}}` 会报错;请改为 `WorkflowRunOptionsPatch(batch_size=5000)`
- 安全边界(`allowed_modules/allowed_functions/resolver_trusted_mode`)不允许在 per-run patch 中覆盖;只能通过 `run_workflow(..., options=RunOptions(...))` 的全局 `options` 提供

失败策略:

- `all_fail`: 任一 run 失败会抛出异常(包装为 `WorkflowRunFailedError`,并通过 `__cause__` 关联原异常)
- `primary_only`: workflow 继续执行,返回值 `outcomes` 中包含成功/失败的可检查结构

并发契约:

- 当 `max_concurrency>1` 且提供了 `components`(hooks/observers)时,系统会在并发执行阶段 capture 事件,并在 workflow 结束后以单线程按稳定顺序 replay 给 components(仍满足 `no-external-callback-under-lock`)
  - components 默认不要求线程安全(同一时刻最多一个回调在执行)
  - 代价: 并发模式下 components 的回调可能非实时(在 replay 阶段触发)
- 如需严格实时回调,请将 `max_concurrency` 设为 `1`
