# YAML DSL Workflow (编排多 demand)

??? note "适用读者"
    - 需要把“多条 demand + Python glue”收敛为可复用编排入口的使用方
    - 需要统一 runs 粒度并发/失败策略/共享 preload cache 治理的开发者

这页讲 **workflow YAML**(编排文件)的语法,以及对应的 Python 运行入口。workflow YAML 和 demand YAML 是两套配置:

- demand YAML: `name/main_source/sources/relations/fields/...`
- workflow YAML: `workflow.runs/resources`(只负责“编排多个 demand”与“声明共享输出资源”)

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
```

语义约束(启动前 fail-fast):

- `workflow.runs` 必须非空
- `workflow.runs[*].id` 必须非空且全局唯一
- `workflow.runs[*].demand` 必须为非空字符串
- workflow 运行期策略(并发/失败策略/调度/cache pool/resources wait/output staging)已迁出 workflow YAML(运行期策略边界),并统一在 Python 入口通过 `WorkflowRunOptions.runtime=WorkflowRuntimeOptions(...)` 配置。
  - workflow YAML 中若出现 `workflow.options.*` 会因 unknown-fields 在 validate/compile 阶段 fail-fast。

### 1.1) `workflow_resources_wait`: 共享资源 join/wait 超时与诊断(runtime entrypoint)

workflow 的共享输出资源(book/csv/sheetbook)在并发模式下会用 joinable inflight 去重 owner 创建；当 owner 卡死/外部 IO 阻塞时,waiter 可能会被挂起。
为避免生产 hang,workflow 默认对 inflight join/wait 启用超时 fail-fast：

- `max_wait_s` 缺省等价于 `600` 秒
- diagnostics 默认禁用(仅当显式开启时才告警)

注意:

- workflow YAML 不再包含 `workflow.options.*`(属于运行期策略边界);如需配置 resources wait,请在 Python 入口使用 `WorkflowRunOptions.runtime=WorkflowRuntimeOptions(resources_wait=...)`。

示例(Python):

```python
from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunSecurityOptions, WorkflowRunOptions, run_workflow
from scalim.dsl.yaml_dsl.workflow_types import WorkflowResourcesWaitDiagnosticsOptions, WorkflowResourcesWaitOptions, WorkflowRuntimeOptions

run_workflow(
    "path/to/workflow.yaml",
    options=WorkflowRunOptions(
        demand=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp"]))),
        runtime=WorkflowRuntimeOptions(
            resources_wait=WorkflowResourcesWaitOptions(
                max_wait_s=600.0,
                diagnostics=WorkflowResourcesWaitDiagnosticsOptions(
                    enabled=True,
                    warn_after_s=30.0,
                    repeat_every_s=60.0,
                    capture_owner_callsite=True,
                ),
            ),
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

- workflow 输出 staging 策略属于运行期策略边界,需通过 `WorkflowRunOptions.runtime=WorkflowRuntimeOptions(output_staging=...)` 配置(不在 YAML 中声明).

示例(Python):

```python
from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunSecurityOptions, WorkflowRunOptions, run_workflow
from scalim.dsl.yaml_dsl.workflow_types import WorkflowOutputStagingOptions, WorkflowRuntimeOptions

run_workflow(
    "path/to/workflow.yaml",
    options=WorkflowRunOptions(
        demand=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp"]))),
        runtime=WorkflowRuntimeOptions(
            output_staging=WorkflowOutputStagingOptions(
                dir_name=".scalim-staging",
                keep_on_success=False,
                keep_on_failure=True,
            ),
        ),
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
- ctx 护栏目前属于内部策略,不在 workflow YAML 中声明,也不作为公开 runtime options 暴露。

需求节点完成时会发布一组稳定的默认 ctx keys(用于减少 Python glue):

- `output_path`(string|null)
- `total_rows`(int|null)
- `duration_secs`(float; seconds)

## 5) `cache_pool`: workflow-scope cache pool

当 `WorkflowRuntimeOptions.cache_pool` 启用时(运行期策略边界;通过 `WorkflowRunOptions.runtime` 配置):

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
  - bounded preset 可选 escape hatch: 强制指定条目常驻到 workflow 结束(v0 仅支持 kind=preload_forever + source_id)
- 预算 `cache_pool.budget`(仅 bounded preset):
  - `max_entries`: entries 数量上限(v0; **必须显式提供**,无隐式默认值)
  - `over_budget_policy`: `fail_fast|evict_lru`(仅淘汰 refcount=0 且未被 `cache_pool.pin` 固定的条目;否则 fail-fast)
- 可观测性: 系统会发出 `workflow_cache_acquire/release/evict` 事件,并复用 `workflow_exec_id/workflow_node_id` 归因字段

对外配置面为 preset-based(封闭集合).典型用法(Python):

```python
from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunSecurityOptions, WorkflowRunOptions, run_workflow
from scalim.dsl.yaml_dsl.workflow_types import (
    WorkflowCachePoolPreloadForeverShared,
    WorkflowCachePoolPreloadForeverUnlimited,
    WorkflowRuntimeOptions,
)

# unlimited: 不施加 entries 数量预算,并等价 `release_policy=workflow_end`(默认常驻到 workflow_end)
unlimited = WorkflowRuntimeOptions(cache_pool=WorkflowCachePoolPreloadForeverUnlimited())

# bounded: 显式预算上限(不再支持通过“大数”模拟无限)
bounded = WorkflowRuntimeOptions(cache_pool=WorkflowCachePoolPreloadForeverShared(max_entries=16))

_ = run_workflow(
    "path/to/workflow.yaml",
    options=WorkflowRunOptions(
        demand=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp.loaders"]))),
        runtime=unlimited,
    ),
)
```

迁移:

- `workflow.options.share_preload_cache` 已移除(旧 YAML 入口不再支持),请改用 `WorkflowRuntimeOptions(cache_pool=...)`

## 6) `workflow.resources.books`: 共享 book 资源（无 `writes`）

workflow YAML 只负责两件事:

- 编排多条 demand(`workflow.runs`)
- 声明 workflow-scope 的共享 IO 资源: `workflow.resources.books`

当前实现里,workflow **不再**提供显式的“写入意图”字段;共享输出的写入由 demand 的 outputs 绑定表达,并由 workflow 编译期推导写入节点。
共享输出的写入顺序与写入语义由 demand YAML 的 outputs 绑定表达,并由 workflow 编译期推导写入节点(确定性、串行化、可冲突检查):

- book 资源声明: `resources.books.<book_id>`
  - 既可以在 demand YAML 声明(standalone 也能跑),也可以在 workflow YAML 的 `workflow.resources.books` 统一声明/覆盖
  - 唯一分支: 统一 `xlsx`（有 `path`=落盘；无 `path`=内存总线）；旧 `xlsx_file` / `xlsx_memory` 已硬删（见 upgrade `2026-07-20-remove-deprecated-xlsx-file-memory-kinds`）
- 输出到 book 的绑定: `outputs[*].to.book` / `outputs[*].to.sheet`
- 写入策略: Python `ResourcesPolicy` / `BookWritePolicy`（`WorkflowRunOptions.resources_policy` 或 `DemandRunOptions.resources_policy`；省略则用 builtin defaults）+ `outputs[*].write`（仅 output-local header 行为: `include_header` / `header_fields_output_by`）

约定:

- CSV 输出使用 `resources.files.<file_id>` + `outputs[*].to.file`
- Excel 输出使用 `resources.books.<book_id>` + `outputs[*].to.book/to.sheet`

注意:

- workflow YAML **不支持** `imports` / `$import` 片段导入(不做 imports expansion)。
- 若需要复用资源声明,优先使用 YAML anchors(`_templates`)或在 demand YAML 中使用 `$import` 生成最终 `resources.*`,workflow 侧仅做声明/覆盖。

示例: workflow 统一声明一个共享落盘 book(`xlsx.path`),各 run 的 demand 只负责声明 outputs 绑定:

说明:
- book cell/sheet `budget` 已**移除**（YAML / `RunOverrides` 残留仍 fail-fast，请删除）；内存风险交宿主 cgroup / OOM / 作业配额。写入策略仍用 Python `BookWritePolicy`（`WorkflowRunOptions.resources_policy`）。

workflow YAML:

```yaml
workflow:
  resources:
    books:
      report:
        xlsx:
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
from scalim.dsl.yaml_dsl import (
    BookResourcePolicy,
    BookWriteMode,
    BookWritePolicy,
    DemandRunOptions,
    DemandRunSecurityOptions,
    ResourcesPolicy,
    WorkflowRunOptions,
    run_workflow,
)

result = run_workflow(
    "path/to/workflow.yaml",
    options=WorkflowRunOptions(
        demand=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp.loaders"]))),
        path_aliases={"@": "/abs/project_root"},
        # 可选: book 写入策略（省略则用 builtin defaults）
        resources_policy=ResourcesPolicy(
            books={
                "report": BookResourcePolicy(
                    write=BookWritePolicy(mode=BookWriteMode.SHEET),
                )
            }
        ),
    ),
)

for outcome in result.outcomes:
    if outcome.error is not None:
        print("FAILED:", outcome.run_id, outcome.error.message)
    else:
        print("OK:", outcome.run_id, outcome.result.total_rows)
```

### 7.1) `patches_by_run_id`: per-run runtime policy(按 run id 注入差异化运行策略)

当 workflow DAG 中存在多个 runs 时,真实生产场景往往需要“不同 run 使用不同运行策略”:

- `batch_size`: 有的 run 更适合小批降低内存峰值,有的 run 更适合大批提升吞吐
- `components`: 仅对某个 run 追加调试 observer/hook(不污染整张图)
- `guardrails/loader_retry/overrides`: 对特定 run 单独加强或关闭

使用方式:在 Python 入口 `run_workflow(..., options=WorkflowRunOptions(patches_by_run_id=...))` 中按 `workflow.runs[*].id` 提供 patch:

- key: `workflow.runs[*].id`(字符串)
- value: **typed** 的 `WorkflowNodePatch`(不支持 dict 形状 patch)
- patch 优先级高于 `WorkflowRunOptions.demand` 的全局默认
- omission / `UNSET` 表示继承;`None` 在支持的字段上表示显式禁用

示例 1: per-run `batch_size` 覆盖全局默认

```python
from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, WorkflowRunOptions, run_workflow
from scalim.dsl.yaml_dsl.workflow_types import WorkflowNodePatch

run_workflow(
    "path/to/workflow.yaml",
    options=WorkflowRunOptions(
        demand=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp.loaders"])),
            runtime=DemandRunRuntimeOptions(batch_size=2000),  # 全局默认
        ),
        patches_by_run_id={"d10_paid_orders": WorkflowNodePatch(batch_size=5000)},  # 仅该 run 用更大 batch
    ),
)
```

示例 2: 仅对某个 run 追加一个调试组件(append,保序)

```python
from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, WorkflowRunOptions, run_workflow
from scalim.dsl.yaml_dsl.workflow_types import ComponentsExtend, WorkflowNodePatch

run_workflow(
    "path/to/workflow.yaml",
    options=WorkflowRunOptions(
        demand=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp.loaders"])),
            runtime=DemandRunRuntimeOptions(components=[my_prod_observer]),
        ),
        patches_by_run_id={"d70_summary_ranking": WorkflowNodePatch(components=ComponentsExtend([my_debug_observer]))},
    ),
)
```

示例 3: 对单个 run 显式禁用全局 `batch_size`(该 run 不分批)

```python
from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, WorkflowRunOptions, run_workflow
from scalim.dsl.yaml_dsl.workflow_types import WorkflowNodePatch

run_workflow(
    "path/to/workflow.yaml",
    options=WorkflowRunOptions(
        demand=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp.loaders"])),
            runtime=DemandRunRuntimeOptions(batch_size=2000),
        ),
        patches_by_run_id={"d20_registered_users": WorkflowNodePatch(batch_size=None)},
    ),
)
```

常见错误与诊断:

- unknown run id: fail-fast 并列出当前 workflow 的合法 ids
- dict patch payload: `patches_by_run_id={"A": {"batch_size": 5000}}` 会报错;请改为 `WorkflowNodePatch(batch_size=5000)`
- 安全边界(`allowed_modules/allowed_functions/resolver_trusted_mode/...`)不允许在 per-run patch 中覆盖;只能通过 `WorkflowRunOptions.demand.security` 的全局 `security` 提供

失败策略:

- `all_fail`: 任一 run 失败会抛出异常(包装为 `WorkflowRunFailedError`,并通过 `__cause__` 关联原异常)
- `primary_only`: workflow 继续执行,返回值 `outcomes` 中包含成功/失败的可检查结构

并发契约:

- 当 `WorkflowRuntimeOptions.execution.max_concurrency>1` 且提供了 `WorkflowRunOptions.workflow_components`(hooks/observers)时,系统会在并发执行阶段 capture 事件,并在 workflow 结束后以单线程按稳定顺序 replay 给这些 components(仍满足 `no-external-callback-under-lock`)
  - workflow_components 默认不要求线程安全(同一时刻最多一个回调在执行)
  - 代价: 并发模式下回调可能非实时(在 replay 阶段触发)
- 如需严格实时回调,请将 `WorkflowRuntimeOptions.execution.max_concurrency` 设为 `1`
