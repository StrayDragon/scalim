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

batch_size: 1000

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
    container: {type: csv, path: ./output/my_report.csv, header_fields_output_by: name}
    fields: [order_id, customer_name, amount, profit]
```

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
- 初始化变量用 `init_vars` 注入并在 `params` 中用 `{$init_var: <name>}` 指令节点引用
- `outputs` 是 **有序列表**(顺序决定 primary 输出); 每个 output 必填唯一 `name`,可用 `from` 复用字段集合与容器配置
- `outputs.*.fields` 是字段选择列表;推荐优先用 `field_id` 字符串以保持稳定与可维护性(允许的形态以 schema 为准)
- `field_id` 必须全局唯一(不再依赖输出层做消歧)
- 分发过滤用 `outputs.*.where`(安全表达式); where 依赖字段会被注入到 required fields

## 相对模块引用(可选)

如果 YAML 文件与 loaders / `call_by` / retry 回调放在同一个 Python 包内,可以用以 `.` / `..` 开头的相对 module 引用来减少 `myapp.xxx` 这种前缀重复:

```yaml
main_source:
  loader: ".loaders:load_orders"

fields:
  status_text:
    call_by: ".helpers:to_text(status)"

retry:
  should_retry: ".retry:should_retry"
```

注意:

- 相对引用以 **YAML 文件所在目录** 为基准,运行期会先归一化为绝对引用,再做 allowlist 校验
- allowlist 仍需要覆盖归一化后的模块前缀(例如 YAML 在 `myapp/reports/` 下, `.loaders:load_orders` 会归一化为 `myapp.reports.loaders:load_orders`)

## 设计偏好

- 输出路径在 `outputs.*.container.path` 显式声明; 多目标共享同一 workbook 时建议开启 `write_lock: true`
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

### list-returning lookup source: `normalize.kind=index_by_key`

当 lookup loader 返回 `list[row]`(而不是 `key -> row` mapping)时,优先在 source 上用 `normalize` 归一化:

```yaml
sources:
  payment_methods:
    loader: "myapp.loaders:load_payment_methods"
    key: payment_method_id
    normalize:
      kind: index_by_key
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
