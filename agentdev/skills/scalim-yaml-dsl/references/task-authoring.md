# YAML 编写

## 何时读取

- 用户要新建 YAML DSL
- 用户要把一段业务逻辑改写成 YAML DSL
- 用户要在现有 YAML 上增删 source / relation / outputs / observability

## 工作顺序

1. 先确认目标字段和最终输出接口
2. 识别 `main_source` 与所有辅助 `sources`
3. 先定义源字段,再定义 relation,最后再写顶层派生字段和 `outputs`
4. 先跑 `schema validate`,再跑 `validate`

## 推荐骨架

```yaml
name: my_report
description: 简短描述

main_source:
  source_id: orders
  loader: "myapp.loaders:load_orders"
  params:
    # 初始化变量注入示例: 由 Python 调用方传入 `init_vars={"end_dt": ...}`.
    end_dt: {$init_var: end_dt}
  fields:
    order_id:
      name: 订单ID
    customer_id:
      name: 客户ID
    amount:
      name: 金额

sources:
  customers:
    loader: "myapp.loaders:load_customers"
    key: customer_id
    params:
      ids: {$keys: {as: set}}
    fields:
      customer_name:
        name: 客户名称
        relation: orders_to_customers

relations:
  orders_to_customers:
    steps:
      - from: orders.customer_id
        to: customers.customer_id

fields:
  profit:
    name: 利润
    compute: "amount - cost"

outputs:
  - name: detail
    to: {file: detail_csv}
    write: {header_fields_output_by: name}
    fields: [order_id, customer_name, amount, profit]

resources:
  files:
    detail_csv:
      csv_file:
        path: {$init_var: out_root}
```

运行期策略提示:

- `batch_size`/`loader_retry`/`guardrails`/demand `failure_policy` 已迁出 YAML 主线(运行期策略边界);请在 runtime entrypoints 中配置:
  - `scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions(..., runtime=DemandRunRuntimeOptions(batch_size=..., loader_retry=..., guardrails=..., demand_failure_policy=...)))`
  - `scalim.dsl.yaml_dsl.run_workflow(..., options=WorkflowRunOptions(demand=DemandRunOptions(..., runtime=DemandRunRuntimeOptions(batch_size=..., loader_retry=..., guardrails=..., demand_failure_policy=...))))`
- workflow 下如需“不同 run 使用不同运行期策略”,请在调用侧使用 `WorkflowRunOptions(patches_by_run_id=...)` 按 `workflow.runs[*].id` 注入 `WorkflowNodePatch`(不支持 dict patch)。

## 关键规则

- `name` 与 `main_source` 必填
- 顶层 `sources` 可省略,缺省视为 `{}`; 但一旦有跨源字段,就必须正确定义 `sources` 与 `relations`
- 顶层 `fields` 只放派生字段
- `main_source.fields` / `sources.<id>.fields` 只放源字段
- whole-result reshape 用 `sources.<id>.normalize`;字段嵌套取值用字段级 `extract`(写在 `main_source.fields.*` / `sources.<id>.fields.*`)
- `relation` 支持 string ref/alias/内联 `steps`:
  - `relation: <relation_id>` 引用 `relations.<relation_id>`
  - `relation: *anchor` (YAML alias)
  - `relation: {steps: [...]}` (内联)
- `steps.from` / `steps.to` 写 `source.field_id`,不要写 loader 的 `data_key`
- 动态入参用 `sources.<id>.params` 模板内联指令节点表达(`$keys` / `$rows`)
- 初始化变量用 `init_vars` 注入,并在 `main_source.params` / `sources.<id>.params` / `resources.files.*.csv_file.path` / `resources.books.*.xlsx_file.path` / `resources.books.*.xlsx_memory.export_xlsx.path` 中用 `{$init_var: <name>}` 指令节点引用(对象节点;编译期解析一次;不做子串插值)
- `outputs` 是 **有序列表**(顺序决定 primary 输出); 每个 output 必填唯一 `name`,可用 `from` 复用字段集合与 `to/write` 编排
- `outputs.*.fields` 是字段选择列表;推荐优先用 `field_id` 字符串以保持稳定与可维护性(允许的形态以 schema 为准)
- `field_id` 必须全局唯一(不再依赖输出层做消歧)
- 分发过滤用 `outputs.*.where`(安全表达式); where 依赖字段会被注入到 required fields

输出路径注入提示:

- `resources.files.*.csv_file.path: {$init_var: ...}` / `resources.books.*.xlsx_file.path` / `resources.books.*.xlsx_memory.export_xlsx.path` 会将“输出 root 决定权”交给调用方;请确保路径在整个 `run()` 生命周期内有效(例如不要指向可能被提前回收的临时目录).

## YAML 模板预编译(可选): `template_vars`

当你需要在 YAML **文本层**使用 `{{ ... }}` / `{% ... %}` 模板语法时(例如未加引号的占位符、条件/循环生成片段),可以让调用方在编译/运行入口传入 `template_vars`。系统会在 **YAML parse 前**用 LiteJinja2 先渲染文本,再进入正常的 parse + 校验/编译流程。

注意事项:

- 仅当调用方显式提供 `template_vars`(非 `None`)时才启用预编译;未提供时不会渲染,避免误把其它系统的 `{{ ... }}` 当模板语法。
- strict-undefined: 模板引用缺失变量会 fail-fast;如需兜底,用 `| default(...)` 显式声明。
- demand 的 `imports/$import` 片段会复用同一份 `template_vars` 做预编译(发生在 fragment YAML parse 前)。
- 当前不提供 `tojson`/`toyaml` 等“安全序列化”过滤器;`template_vars` 渲染结果必须是合法 YAML 文本。

示例(渲染后仍需能通过 schema/语义校验):

```yaml
resources:
  files:
    detail_csv:
      csv_file:
        path: {{ out_root | default("./output") }}

outputs:
  - name: detail
    to: {file: detail_csv}
    fields: [order_id]
```

调用侧(Python):

```py
from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunSecurityOptions, DemandRunTemplateOptions, run

run(
    "report.yaml",
    options=DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp"])),
        template=DemandRunTemplateOptions(template_vars={"out_root": "./out"}),
    ),
)
```

## 相对模块引用(可选)

如果 YAML 文件与 loaders / `call_by` 放在同一个 Python 包内,可以用以 `.` / `..` 开头的相对 module 引用来减少 `myapp.xxx` 这种前缀重复:

```yaml
main_source:
  loader: ".loaders:load_orders"

fields:
  status_text:
    call_by: ".helpers:to_text(status)"
```

注意:

- 相对引用以 **YAML 文件所在目录** 为基准,运行期会先归一化为绝对引用,再做 allowlist 校验
- allowlist 仍需要覆盖归一化后的模块前缀(例如 YAML 在 `myapp/reports/` 下, `.loaders:load_orders` 会归一化为 `myapp.reports.loaders:load_orders`)

`loader_retry`/`guardrails` 等运行期策略已迁出 YAML,调用侧可直接在 Python 中导入回调/策略对象并注入:

```py
from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, compile
from scalim.execution.loader_retry import LoaderRetryPoliciesSpec, LoaderRetryPolicySpec

from myapp.reports import retry as retry_mod

compile(
    "report.yaml",
    options=DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp"])),
        runtime=DemandRunRuntimeOptions(loader_retry=LoaderRetryPoliciesSpec(default=LoaderRetryPolicySpec(should_retry=retry_mod.should_retry))),
    ),
)
```

## 设计偏好

- CSV/Excel 输出 root 在 `resources.files.*.path` / `resources.books.*.(path|export_xlsx.path)` 显式声明(版本化输出 D-2)
- 多 outputs 共享同一 book 输出时,用 `to.book/to.sheet` 明确绑定;并发写同一 root 依赖“版本目录隔离”(通过 `scalim.shortcuts.resources.outputs` 定位最新产物,或显式指定版本目录)
- 优先使用 string ref / string sugar;仅在需要大段复用/覆写时再用 anchor
- 输出字段优先显式声明(避免隐式全量导出);简单场景可用 string sugar
- 只有在 DSL 无法表达时才退回 Python

## 常见模式

### 单级关联

```yaml
relations:
  orders_to_customers:
    steps:
      - from: orders.customer_id
        to: customers.customer_id
```

### 多级关联

```yaml
relations:
  orders_to_regions:
    steps:
      - from: orders.warehouse_id
        to: warehouses.warehouse_id
      - from: warehouses.region_id
        to: regions.region_id
```

### 复合键关联

```yaml
relations:
  orders_to_price:
    steps:
      - from: [orders.region_id, orders.product_category_id]
        to: [price.region_id, price.product_category_id]
```

### list-returning lookup source: `normalize.index_by_key`

当 lookup loader 返回 `list[row]`(而不是 `key -> row` mapping)时,优先在 source 上用 `normalize` 归一化:

```yaml
sources:
  payment_methods:
    loader: "myapp.loaders:load_payment_methods"
    key: payment_method_id
    normalize:
      index_by_key:
        key_field: payment_method_id
        on_conflict: error
```

字段级 `extract` 仍然只负责从“单条 row value”里取字段:

```yaml
fields:
  payment_method_name:
    extract: payment_method_name
```

### `$rows` 注入 batch rows

```yaml
sources:
  customers_rows:
    loader: "myapp.loaders:load_customers_by_rows"
    key: customer_id
    params:
      rows: {$rows: {cache_mode: batch}}
    fields:
      customer_name:
        name: 客户名称
        relation:
          steps:
            - from: orders.customer_id
              to: customers_rows.customer_id
```

### 派生字段

```yaml
fields:
  order_amount:
    name: 订单金额
    compute: "quantity * unit_price"

  tax_amount:
    name: 税费
    compute: "order_amount * tax_rate"
```

## 不要这样写

- 不要在 `top-level fields` 放源字段(源字段请写在 `main_source.fields` / `sources.<id>.fields`)
- 不要使用 legacy `$runtime.<name>` 字符串占位符
- 不要把 `data_key` 写进 relation steps
- 不要把 allowlist 当成 YAML 字段写进配置
- 不要为了复用就默认拆出 `_loaders.py` / `_helpers.py` / `_adapters.py`

## 编写完成后的最小检查

```bash
uv run scalim-cli yaml-dsl schema validate <file.yaml>
uv run scalim-cli yaml-dsl validate <file.yaml>
```

需要全量字段、definitions、enum/default/examples 时再读:

- [syntax-catalog.gen.md](syntax-catalog.gen.md)
- [generated/cli-lsp-reference.gen.md](generated/cli-lsp-reference.gen.md)
- [generated/example-full/ecommerce_report.gen.yaml](generated/example-full/ecommerce_report.gen.yaml)
