# YAML DSL Workflow (编排多 demand)

??? note "适用读者"
    - 需要把“多条 demand + Python glue”收敛为可复用编排入口的使用方
    - 需要统一 runs 粒度并发/失败策略/共享 preload cache 治理的开发者

这页讲 **workflow YAML**(编排文件)的语法,以及对应的 Python 运行入口。workflow YAML 和 demand YAML 是两套配置:

- demand YAML: `name/main_source/sources/relations/fields/...`
- workflow YAML: `workflow.runs/options`(只负责“编排多个 demand”)

## 1) 最小结构

```yaml
# $schema: ../schema/workflow.gen.json

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
- 支持通过 Python 入口注入 `path_aliases` 来解析:
  - `"@/x/y.yaml"` (alias 为 `"@"`)
  - `"ALIAS:/x/y.yaml"` (alias 为 `"ALIAS"`)

## 3) Python 运行入口

当前暂不扩展 CLI; 先用 Python 入口:

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

## 4) `cache_pool`: workflow-scope cache pool

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
  - `pin`: 可选 escape hatch,强制指定条目常驻到 workflow 结束
- 预算 `cache_pool.budget`:
  - `max_entries`: entries 数量上限(v0)
  - `over_budget_policy`: `fail_fast|evict_lru`(仅淘汰 refcount=0 且未 pin 的条目;否则 fail-fast)
- 可观测性: 系统会发出 `workflow_cache_acquire/release/evict` 事件,并复用 `workflow_exec_id/workflow_node_id` 归因字段

迁移:

- `workflow.options.share_preload_cache` 已移除,请改用 `workflow.options.cache_pool`
