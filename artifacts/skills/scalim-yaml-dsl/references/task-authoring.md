# YAML Authoring

## 何时读取

- 用户要新建 YAML DSL
- 用户要把一段业务逻辑改写成 YAML DSL
- 用户要在现有 YAML 上增删 source / relation / output / observability

## 工作顺序

1. 先确认目标字段和最终输出接口
2. 识别 `main_source` 与所有辅助 `sources`
3. 先定义源字段,再定义 relation,最后再写顶层派生字段和 `output.fields`
4. 先跑 `schema validate`,再跑 `validate`

## 推荐骨架

```yaml
name: my_report
description: 简短描述

batch_size: 1000

main_source:
  source_id: orders
  loader: "myapp.loaders:load_orders"
  fields:
    order_id: &order_id
      name: 订单ID
    customer_id:
      name: 客户ID
    amount: &amount
      name: 金额

sources:
  customers:
    loader: "myapp.loaders:load_customers"
    key: customer_id
    bind:
      use_keys:
        param: ids
    fields:
      customer_name: &customer_name
        name: 客户名称
        relation: *orders_to_customers

relations:
  orders_to_customers: &orders_to_customers
    steps:
      - from: orders.customer_id
        to: customers.customer_id

fields:
  profit: &profit
    name: 利润
    compute: "amount - cost"

output:
  fields:
    - *order_id
    - *customer_name
    - *amount
    - *profit
```

## 关键规则

- `name` 与 `main_source` 必填
- 顶层 `sources` 可省略,缺省视为 `{}`; 但一旦有跨源字段,就必须正确定义 `sources` 与 `relations`
- 顶层 `fields` 只放派生字段
- `main_source.fields` / `sources.<id>.fields` 只放源字段
- `relation` 只能写 YAML alias 或内联 `steps`,不要写字符串 relation_id
- `steps.from` / `steps.to` 写 `source.field_id`,不要写 loader 的 `data_key`
- `bind` / `to_bind` 只能二选一使用 `use_keys` 或 `use_rows`
- `output.fields` 每项必须是对象或 alias,不能写纯字符串
- 跨 source 同名 `field_id` 时,`output.fields` 里必须显式加 `source`

## 设计偏好

- 优先把 YAML 当模板使用,输出路径尽量交给 Python `overrides.output.*`
- 优先给需要复用的字段对象和 relation 对象打 anchor
- 输出字段优先写 alias 或显式对象,不要依赖隐式全量导出
- 只有在 DSL 无法表达时才退回 Python

## 常见模式

### 单级关联

```yaml
relations:
  orders_to_customers: &orders_to_customers
    steps:
      - from: orders.customer_id
        to: customers.customer_id
```

### 多级关联

```yaml
relations:
  orders_to_regions: &orders_to_regions
    steps:
      - from: orders.warehouse_id
        to: warehouses.warehouse_id
      - from: warehouses.region_id
        to: regions.region_id
```

### 复合键关联

```yaml
relations:
  orders_to_price: &orders_to_price
    steps:
      - from: [orders.region_id, orders.product_category_id]
        to: [price.region_id, price.product_category_id]
```

### `use_rows` 绑定

```yaml
sources:
  customers_rows:
    loader: "myapp.loaders:load_customers_by_rows"
    key: customer_id
    fields:
      customer_name:
        name: 客户名称
        relation:
          steps:
            - from: orders.customer_id
              to: customers_rows.customer_id
              to_bind:
                use_rows:
                  param: rows
                  cache_mode: batch
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

- 不要在 `top-level fields` 放 `field: xxx`
- 不要在 `output.fields` 里写 `- order_id`
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
