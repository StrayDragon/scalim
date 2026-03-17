# YAML DSL Workflow (编排多 demand)

??? note "适用读者"
    - 需要把“多条 demand + Python glue”收敛为可复用编排入口的使用方
    - 需要统一 runs 粒度并发/失败策略/共享 preload cache 的开发者

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
    share_preload_cache: true
```

语义约束(启动前 fail-fast):

- `workflow.runs` 必须非空
- `workflow.runs[*].id` 必须非空且全局唯一
- `workflow.runs[*].demand` 必须为非空字符串
- `workflow.options.max_concurrency` 必须为整数且 >= 1(默认 `1`)
- `workflow.options.failure_policy` 为 `all_fail` 或 `primary_only`(默认 `all_fail`)
- `workflow.options.share_preload_cache` 默认 `false`

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

## 4) `share_preload_cache`: 跨 runs 共享 `preload_forever`

当 `workflow.options.share_preload_cache=true` 时:

- 同一 workflow 执行内,相同 `source_id` 的 `cache_mode: preload_forever` 只会真实加载一次,其余 runs 复用结果
- 系统会在执行任一 run 之前做“规格签名一致性”预检查:
  - 若同一 `source_id` 在不同 runs 的 preload 规格不一致(例如 loader/params/normalize/key/lookup_cast 等关键字段不同),将 fail-fast 报错
  - 错误信息会包含冲突 run id 与差异点
