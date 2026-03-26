# YAML DSL 用户指导文档

??? note "适用读者"
    - 写 YAML 配置并运行任务的使用方开发者/数据运营/数据同学
    - 需要理解运行时安全边界与排错入口的集成方

??? note "维护提示"
    本页内容通常会在以下变更后需要同步检查:

    - YAML DSL 的 JSON Schema 与语义校验规则变更
    - `loader` / `call_by` 的解析与 allowlist 规则变更
    - `outputs` / `observability` 等关键字段的结构与默认值变更

## 目录

- [快速开始](#1-quick-start)
- [核心概念](#2-core-concepts)
- [配置详解](#3-configuration-reference)
- [高级特性](#4-advanced-features)
- [完整示例](#5-complete-examples)
- [最佳实践](#6-best-practices)
- [常见问题](#7-faq)

---

## 1. 快速开始 (Quick Start)

### 1.1 什么是 YAML DSL

Scalim YAML DSL 是一个用于配置数据关联和报表生成的声明式配置语言.通过简单的 YAML 配置,您可以:

- 定义多个数据源及其关联关系
- 自动执行数据查询和关联
- 生成 CSV/Excel 报表
- 监控性能和执行状态

### 1.2 第一个示例:最小可运行配置

下面给出两个层次的示例:

**最小模板示例**(仅包含必填字段;顶层 `sources` 可缺省并视为 `{}`;推荐把 `YAML` 当作模板使用,不声明 `outputs`):

```yaml
name: minimal_order_report

main_source:
  source_id: orders
  loader: "myapp.loaders:load_orders"
  fields:
    order_id:
      name: 订单ID
```

如果希望写文件输出,推荐在 Python 调用侧使用与 YAML `outputs` 同形的 `overrides.outputs` 指定输出编排(字段/路径/sheet/表头策略等),而不是把路径写死在 YAML 里:

```python
from scalim.dsl.by_yaml import RunOverrides, run

result = run(
    "path/to/config.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
    overrides=RunOverrides(
        outputs=[
            {
                "name": "detail",
                "container": {"type": "workbook", "path": "./output/minimal_order_report.xlsx", "sheet": "明细"},
                "fields": ["order_id"],
            }
        ]
    ),
)
```

当然,也可以在 YAML 内固定输出路径(可选;使用 `outputs`):

```yaml
outputs:
  - name: detail
    container: {type: workbook, path: ./output/minimal_order_report.xlsx, sheet: 明细}
    fields: [order_id]
```

**更完整示例**(包含 sources/relations/derived fields/outputs):

```yaml
name: simple_order_report
description: 简单订单报表

main_source:
  source_id: orders
  loader: "myapp.loaders:load_orders"
  params:
    begin_time: "2024-01-01"
    end_time: "2024-01-31"
  fields:
    order_id:
      name: 订单ID
    amount:
      name: 订单金额

sources:
  customers:
    loader: "myapp.loaders:load_customers"
    key: customer_id
    params:
      customer_ids: {$keys: {as: set}}
    fields:
      customer_name:
        name: 客户名称

relations:
  orders_to_customers:
    steps:
      - from: orders.customer_id
        to: customers.customer_id

fields:
  total_amount:
    name: 总金额
    compute: "sum(amount)"

outputs:
  - name: detail
    container: {type: csv, path: ./output/order_report.csv, header_fields_output_by: name}
    fields: [order_id, customer_name, amount, total_amount]
```

### 1.3 运行配置的方法

**安装 CLI 工具**:

```bash
uv tool install --editable <PATH_TO_SCALIM>/scalim[cli]
```

**运行配置**:

```bash
# 验证配置语法
scalim-cli yaml-dsl validate config.yaml
```

更多 CLI 子命令与参数说明以 `scalim-cli yaml-dsl --help` / `scalim-cli yaml-dsl validate --help` 为准.

**Python 代码调用**:

```python
from scalim.dsl.by_yaml import RunOverrides, run

# 加载并执行 YAML 配置(安全:需要 allowlist)
result = run(
    "path/to/config.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
)

# 常见用法: YAML 不声明 outputs,由 Python overrides.outputs 指定单输出编排(推荐)
result = run(
    "path/to/config.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
    overrides=RunOverrides(
        outputs=[
            {
                "name": "detail",
                "container": {"type": "csv", "path": "./output/order_report.csv"},
                "fields": ["order_id"],
            }
        ]
    ),
)
```

`init_vars` 注入(用于解析 `{$init_var: <name>}` 指令节点;**对象节点**、仅编译期解析一次、不做子串插值):

```yaml
main_source:
  params:
    end_dt: {$init_var: end_dt}
```

`outputs.*.container.path` 也支持同样的注入语法:

```yaml
outputs:
  - name: detail
    container:
      type: workbook
      path: {$init_var: output_path}
      sheet: 明细
    fields: [order_id]
```

```python
from datetime import datetime

result = run(
    "path/to/config.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
    init_vars={
        "end_dt": datetime(2024, 1, 31),
        "output_path": "./output/report.xlsx",
    },
)
```

指令节点范围约束(稳定 authoring surface):

| 位置 | `{$init_var: ...}` | `{$keys: ...}` | `{$rows: ...}` |
|---|---|---|---|
| `main_source.params` | ✅ | ❌ | ❌ |
| `sources.<id>.params` | ✅ | ✅ | ✅ |
| `outputs.*.container.path` | ✅ | ❌ | ❌ |

---

## 2. 核心概念 (Core Concepts)

### 2.1 主数据源 (main_source)

主数据源是报表的数据起点,类似 SQL 中的 `FROM` 子句.它定义了:

- **source_id**: 数据源唯一标识
- **loader**: 加载数据的 Python 函数
- **fields**: 主数据源包含的字段

### 2.2 数据源 (sources)

数据源定义了可通过关联访问的辅助数据表.每个数据源需要:

- **loader**: 数据加载函数
- **key**: 主键字段(支持复合键)
- **normalize**: whole-result 归一化(可选;在字段级 `extract` 之前执行)
- **params**: loader kwargs 模板(可用 `{$init_var: <name>}` / `$keys/$rows` 表达动态上下文)

### 2.3 字段类型

Scalim YAML DSL 支持两种字段类型:

#### 源字段 (Source Fields)
直接来自数据源的字段,定义在 `main_source.fields` 或 `sources.<id>.fields` 中:

```yaml
main_source:
  fields:
    order_id:
      extract: order_id    # 可省略: 缺省等价于 extract: <field_id>
      name: 订单ID          # 显示名称
      value_cast: int      # 值转换(可选)
```

#### 派生字段 (Derived Fields)
通过计算表达式生成的字段,定义在顶层 `fields` 中:

```yaml
fields:
  profit:
    name: 利润
    compute: "amount - cost"  # Python 表达式(使用 field_id 作为变量;依赖从表达式推导)
```

### 2.4 关联关系 (relations)

关联定义了如何在数据源之间建立连接,类似 SQL JOIN:

```yaml
relations:
  orders_to_customers:
    steps:
      - from: orders.customer_id    # 上游字段
        to: customers.customer_id   # 下游字段
```

补充: main_source 侧 join key 允许使用受限的 derived fields:

- 仅允许在 `from` 侧引用顶层 `fields.*` 派生字段(语法仍为 `source.field`),且 `source` 必须等于 `main_source.source_id`
- 该 derived field 必须是 **pre-relation 可计算**(依赖闭包不能包含 ref 字段/带 relation 的字段),否则会在编译/校验阶段 fail-fast
- `to` 侧仍不允许引用 derived fields

**支持多种关联类型**:

- **单级关联**: `A → B`
- **多级关联**: `A → B → C`
- **复合键关联**: `[f1, f2] → [k1, k2]`

### 2.5 输出配置 (outputs)

定义报表的多输出编排(有序列表),支持 workbook 多 sheet 分发(where)与派生汇总(aggregate):

```yaml
meta: true
audit: true

outputs:
  - name: detail
    container:
      type: workbook
      path: ./output/report.xlsx
      sheet: 明细
      header_fields_output_by: name
      write_lock: true
    fields: [order_id, customer_name, amount]

  - name: direct
    from: detail
    container:
      type: workbook
      path: ./output/report.xlsx
      sheet: 直客
      write_lock: true
    where: "channel == 'direct'"

  - name: by_channel
    container:
      type: workbook
      path: ./output/report.xlsx
      sheet: 渠道汇总
      write_lock: true
    aggregate:
      group_by: [channel]
      fields:
        order_cnt: {count: {}}
        sum_amount: {sum: {field: amount}}
```

---

## 3. 配置详解 (Configuration Reference)

### 3.1 顶层配置

顶层字段集合、`required` 边界与默认值以 JSON Schema 为准(避免文档漂移):

- [YAML Schema 参考(生成)](schema-reference.gen.md) (Top-Level Fields / Definitions)
- CLI 导出 schema: `scalim-cli yaml-dsl schema show` / `scalim-cli yaml-dsl schema path`

最小必填字段只有:

- `name`
- `main_source`

**示例**:

```yaml
name: order_report
description: 订单报表配置
batch_size: 500

_templates:
  # 定义可复用的 YAML 锚点
  common_params_keys: &common_params_keys
    ids: {$keys: {as: set}}
```

### 3.2 主数据源配置 (main_source)

`main_source` 必须包含:

- `source_id` (required)
- `loader` (required)

完整字段集合/默认值见: [YAML Schema 参考(生成)](schema-reference.gen.md) 中的 `main_source` definition.

**loader 引用格式**:

- `module.path:ClassName` - 类
- `module.path:function` - 函数
- `module.path:obj.method` - 对象方法

**示例**:

```yaml
main_source:
  source_id: orders
  loader: "myapp.loaders:load_orders"
  params:
    begin_time: "2024-01-01"
    end_time: "2024-01-31"
    status: "completed"
  fields:
    order_id:
      name: 订单ID
    customer_id:
      name: 客户ID
    amount:
      name: 订单金额
      value_cast: int
```

### 3.3 数据源配置 (sources)

顶层 `sources` 为可选字段;未提供时等价于空映射 `{}`.

每个 source 必填:

- `loader`
- `key` (支持复合键)

完整字段集合/默认值见: [YAML Schema 参考(生成)](schema-reference.gen.md) 中的 `source` definition.

#### 3.3.1 loader kwargs 模板 (params)

Scalim 将 loader 的调用参数收敛到 `params` kwargs 模板:

- `main_source.params`: 直接以 kwargs 传给 main source loader
  - 支持 `{$init_var: <name>}` 指令节点(编译期解析)
  - 禁止 `$keys/$rows`
- `sources.<id>.params`: loader kwargs 模板
  - 支持 `{$init_var: <name>}` 指令节点(编译期解析;单键映射;不做子串插值)
  - 支持 `$keys` 注入 lookup keys(可出现在任意嵌套位置):
    - `{$keys: {as: set|list}}`(默认 set)
    - `$keys.as=list` 会输出稳定顺序列表
    - composite key 注入为 tuple 元素
  - 支持 `$rows` 注入批次行上下文(可出现在任意嵌套位置):
    - `{$rows: {cache_mode: batch|none}}`(默认 batch)
    - `$rows` 会触发 rows barrier: `parallel_mode="adaptive"` 时该层 LoadRef 串行执行
    - `$rows.cache_mode=none` 会禁用批次内 relation 复用(每个字段各自调用 loader)

```yaml
sources:
  customers:
    loader: "myapp.loaders:load_customers"
    key: customer_id
    params:
      customer_ids_set: {$keys: {as: set}}
```

`$rows` 示例(注意 barrier 语义):

```yaml
sources:
  customers:
    loader: "myapp.loaders:load_customers_by_rows"
    key: customer_id
    params:
      rows: {$rows: {cache_mode: batch}}
```

#### 3.3.2 缓存模式 (cache_mode)

取值与默认值见: [YAML Schema 参考(生成)](schema-reference.gen.md) 中的 `source.cache_mode`.

语义:

- `none`: 不缓存,每次关联都重新查询
- `preload_forever`: 预加载并永久缓存(若 `params` 非空会透传 kwargs;为空则保持零参 preload)

#### 3.3.3 键值归一化 (lookup_cast)

用于在关联前对键值进行类型转换或归一化:

```yaml
sources:
  regions:
    loader: "myapp.loaders:load_regions"
    key: region_id
    lookup_cast:
      name: int                # 转换类型:auto/int/str/sep_first
```

**转换类型**:

- `auto`: 自动归一化
- `int`: 转为整数
- `str`: 转为字符串
- `sep_first`: 按分隔符截取首段再归一化

**注意(float key)**:

- `auto` 会拒绝 float lookup key(返回 None 并忽略该键),以避免 `123.0` 与 `123` 的歧义.
- 若你的外键可能以 float 形式出现(例如 JSON/YAML 数字、上游系统返回 123.0),请显式使用 `lookup_cast: {name: int|str}` 或在 loader 中修复类型.

**sep_first 示例**:

```yaml
# 处理 "1,2,3" 这样的 CSV 多值字段
lookup_cast:
  name: sep_first
  sep: ","          # 默认 ","
```

#### 3.3.4 整体结果归一化 (normalize)

`normalize` 是 **源代码级** 的整体结果归一化: 作用于整个 `loader` 返回值,并且发生在字段级 `extract` 之前.

支持的写法(按复杂度由低到高):

- `kind: index_by_key`: 将 `list[row]` 归一化为 `lookup_key -> row` 映射
  - `key_field`: 从每个 row 中读取 lookup key 的字段名(必填)
  - `on_conflict`: duplicate key 策略,可选 `error|first|last`(默认 `error`)
- `kind: take_first`: 将 `mapping[key -> list[row]]` 归一化为 `mapping[key -> row]`
  - `on_empty`: 空列表策略,可选 `miss|null|error`(默认 `miss`)
  - 注意: 顶层 `list[row]` 场景仍应使用 `index_by_key`
- `kind: project_fields`: 对 `mapping[key -> row]` 的 row value 做投影/重命名
  - `fields`: 投影规则映射,每个字段用 `from_key` 或 `extract` 二选一
  - `on_missing`: 缺失路径策略,可选 `error|null`(默认 `error`)
  - `extract` 的语法与字段级 `extract` 一致(支持 int-key path,例如 `"[1].x"`)
- `kind: map_values`: 对 `mapping` 的 values 批量应用 normalize steps(当前支持 `take_first` / `project_fields`)
  - `steps`: step 列表(按顺序执行)
- 可选扩展点: `call_by`
  - whole-result `Mapping -> Mapping`,引用解析与 `loader` 一致(支持相对引用,并受 allowlist 约束)
  - 用于 declarative normalize 难以表达但不想写 wrapper module 的场景

示例: loader 返回 `list[row]`,用 `normalize.kind=index_by_key` 归一化为映射

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

示例: `mapping[key -> list[row]]` 用 `take_first` 取首条

```yaml
normalize:
  kind: take_first
  on_empty: miss  # miss|null|error
```

示例: nested dict 拍平/重命名(`project_fields`)

```yaml
normalize:
  kind: project_fields
  on_missing: error  # error|null
  fields:
    order_id: {from_key: true}
    customer_level: {extract: "[1].clearn_reason_level"}
    operation_level: {extract: "[2].clearn_reason_level"}
    review_status: {extract: review_status}
```

示例: values pipeline(`map_values`: take_first + project_fields)

```yaml
normalize:
  kind: map_values
  steps:
    - kind: take_first
      on_empty: miss
    - kind: project_fields
      on_missing: error
      fields:
        order_id: {from_key: true}
        review_status: {extract: review_status}
```

边界说明:
- `normalize` 只负责“把整个返回值整理成可用于 `lookup` 的形状”;它不负责从单条 `row` 里取字段
- 从单条 `row` 里取字段请用字段级 `extract`(定义在 `sources.<id>.fields.*` / `main_source.fields.*`)

### 3.4 字段配置

#### 3.4.1 源字段 (Source Fields)

在 `main_source.fields` 或 `sources.<id>.fields` 中定义:

常用 key:

- `extract`: 从当前 source row 中取值的路径表达式(可省略;缺省等价于 `extract: <field_id>`)
- `name`: 显示名称(可选)
- `value_cast`: 值转换(可选)
- `relation`: 关联路径或 YAML 别名引用(可选)

完整字段集合/默认值见: [YAML Schema 参考(生成)](schema-reference.gen.md) 中的 `field` / `source_field_inline` definition.

**extract 的默认与语法**:

<!-- BEGIN AUTOGEN:yaml-dsl-source-field-extract -->
从当前 key 对应的 row value 中提取字段值的路径表达式(不是相对整个 loader-result mapping).

语法: dot + bracket path(建议写成字符串,避免 YAML 歧义):
- `extract` 省略时,等价于 `extract: <field_id>`(顶层同名 key)
- dot: `a.b.c`
- int-key: `"[1].clearn_reason_level"` (表示 key=1,不是 list index)
- 字面量 string key: `'["a.b"].x'` (用于 key 本身包含点号等特殊字符)

注意:
- 不做 `"1"` ↔ `1` 的隐式转换(避免歧义)
- 不支持数组/列表下标语义: `[1]` 永远表示 “key=1”
- 缺失/路径不匹配时返回 `None`

示例(含嵌套取值):

```yaml
main_source:
  fields:
    # 顶层同名 key: extract 可省略
    review_status:
      name: 审核状态

    # int-key nested dict: role_id 是 int(例如 1/2)
    customer_clearn_reason_level:
      name: 客户净利原因等级
      extract: "[1].clearn_reason_level"

    # dotted literal key: row 的 key 就叫 "a.b"
    dotted_literal_key_value:
      extract: '["a.b"].x'
```

示例(给定 loader 返回值,extract 提取后的输出长什么样):

```python
result = {
  1: {1: {"clearn_reason_level": 2}, 2: {"clearn_reason_level": 1}, "review_status": 0},
}
```

字段:

```yaml
sources:
  clearn_reasons:
    fields:
      customer_level:
        extract: "[1].clearn_reason_level"
      operation_level:
        extract: "[2].clearn_reason_level"
      review_status:
        extract: review_status
```

对 `lookup_key=1` 的 row value:
- `customer_level` → `2`
- `operation_level` → `1`
- `review_status` → `0`

最终输出行片段:

```python
{"customer_level": 2, "operation_level": 1, "review_status": 0}
```

补充边界:
- 如果中间段是 list/tuple, `"[1]"` 也不会当作下标(会返回 `None`)
- 如果同时存在 key `"1"` 与 `1`,需要用 `extract: '["1"].x'` 与 `extract: "[1].x"` 明确区分
<!-- END AUTOGEN:yaml-dsl-source-field-extract -->

**示例**:

```yaml
main_source:
  fields:
    order_id:
      name: 订单ID
    customer_id:
      name: 客户ID

sources:
  customers:
    fields:
      customer_name:
        name: 客户名称
        relation: *orders_to_customers  # YAML 别名引用
      customer_level:
        name: 会员等级
        value_cast: str
        relation:
          steps:               # 内联关系定义
            - from: orders.customer_id
              to: customers.customer_id
```

#### 3.4.2 派生字段 (Derived Fields)

在顶层 `fields` 中定义:

必须二选一:

- `compute`: Python 表达式(使用 field_id 作为变量)
- `call_by`: 函数调用:`reference(args...)`(支持 kwargs / Python 字面量 / `$ctx`)

可选:

- `name`: 显示名称

完整字段集合/默认值见: [YAML Schema 参考(生成)](schema-reference.gen.md) 中的 `field` definition.

> 注: `depends_on` 不再作为用户侧配置字段.派生字段依赖由系统从 `compute` 表达式中自动推导;若配置中出现 `depends_on`,校验会失败.

**示例**:

```yaml
fields:
  profit:
    name: 利润
    compute: "amount - cost"

  status_text:
    name: 状态文本
    call_by: "myapp.enums:get_status_text(status=status, ctx=$ctx)"

  profit_margin:
    name: 利润率
    compute: "(amount - cost) / amount * 100 if amount > 0 else 0"

  final_price:
    name: 最终价格
    compute: "order_amount * price_adjustment + shipping_fee"
```

### 3.5 关联配置 (relations)

#### 3.5.1 命名关系模板

在顶层 `relations` 中定义可复用的关系模板:

```yaml
relations:
  orders_to_customers:
    steps:
      - from: orders.customer_id
        to: customers.customer_id

  orders_to_categories:  # 多级关联
    steps:
      - from: orders.product_id
        to: products.product_id
      - from: products.category_id
        to: categories.category_id

  orders_to_region_pricing:  # 复合键关联
    steps:
      - from: [orders.region_id, orders.product_category_id]
        to: [region_pricing.region_id, region_pricing.product_category_id]
```

#### 3.5.2 内联关系

直接在字段中定义关系:

```yaml
sources:
  customers:
    fields:
      customer_name:
        name: 客户名称
        relation:
          steps:
            - from: orders.customer_id
              to: customers.customer_id
```

#### 3.5.3 关系步骤属性 (Step Properties)

每个 step 必填:

- `from` (支持列表用于复合键)
- `to` (支持列表用于复合键)

可选:

- `lookup_cast`: 键值归一化转换

完整字段集合/默认值见: [YAML Schema 参考(生成)](schema-reference.gen.md) 中的 `relation` definition.

**重要: steps 中的 `source.field` 使用 field_id**

`from/to` 里写的 `orders.customer_id` / `customers.customer_id` 中 `customer_id` 指的是字段的 **field_id(YAML key)**,不是字段配置里的 `extract:`(data_key/路径表达式).

当你做了重命名(`field_id != extract`)时,steps 仍然引用 `field_id`:

```yaml
main_source:
  source_id: orders
  loader: "myapp.loaders:load_orders"
  fields:
    customer_id:
      extract: customer_id_col  # data_key

sources:
  customers:
    loader: "myapp.loaders:load_customers"
    key: customer_id
    params:
      ids: {$keys: {as: set}}
    fields:
      customer_id:
        extract: id  # data_key

relations:
  orders_to_customers:
    steps:
      - from: orders.customer_id     # field_id
        to: customers.customer_id    # field_id
```

**示例**:

```yaml
sources:
  customers:
    loader: "myapp.loaders:load_customers"
    key: customer_id
    params:
      ids: {$keys: {as: list}}

steps:
  - from: orders.customer_id
    to: customers.customer_id
    lookup_cast:
      name: int
```

#### 3.5.4 关联类型

**单级关联**:

```yaml
relations:
  orders_to_customers:
    steps:
      - from: orders.customer_id
        to: customers.customer_id
```

**多级关联**:

```yaml
relations:
  orders_to_countries:
    steps:
      - from: orders.pay_id
        to: pays.pay_id
      - from: pays.country_id
        to: countries.country_id
```

**复合键关联**:

```yaml
relations:
  orders_to_region_pricing:
    steps:
      - from: [orders.region_id, orders.product_category_id]
        to: [region_pricing.region_id, region_pricing.product_category_id]
```

**CSV 多值字段关联**:

```yaml
relations:
  orders_to_small_groups:
    steps:
      - from: orders.small_group_ids
        to: small_groups.small_group_id
        lookup_cast:
          name: sep_first
          sep: ","
```

### 3.6 输出配置 (outputs)

`outputs` 可省略;声明后进入 composed outputs 模式.常用字段:

- `outputs`: 有序列表(顺序决定 primary 输出)
- `outputs.*.container`: 输出容器(workbook/csv)与路径/工作表等
- `outputs.*.fields`: 明细输出的导出列顺序(field_id 列表)
- `outputs.*.where`: 安全表达式过滤(用于分发多 sheet)
- `outputs.*.aggregate`: 派生汇总输出(与 `fields` 互斥)

完整字段集合/默认值见: [YAML Schema 参考(生成)](schema-reference.gen.md) 中的 `outputs` / `output_container` / `output_target` definitions.

**示例**:

```yaml
outputs:
  - name: detail
    container: {type: csv, path: ./output/order_report.csv, header_fields_output_by: name}
    fields: [order_id, customer_name, amount, profit]
```

### 3.7 可观测性配置 (observability)

#### 3.7.1 日志配置 (logging)

```yaml
observability:
  logging:
    enabled: true            # 启用日志观测(当 logging 块存在时默认 true)
    renderer: pretty         # pretty/logger (默认 pretty)
```

注意: Scalim 默认不会注册 logging observer(默认静默).只有当你在 YAML 中声明 `observability.logging` 时才会输出执行进度日志.

- `renderer: pretty`: 输出到 pretty console(如 panel/table)
- `renderer: logger`: 输出到标准 logger

#### 3.7.2 性能监控 (performance)

```yaml
observability:
  performance:
    enabled: true
    metrics: [duration, memory, cpu]    # 指标类型
    sampling_interval: 1                 # 采样间隔(批次数)
    report:
      format: csv                       # 报告格式:console/json/csv/none
      output: ./output/perf_report.csv
      include_details: true
    thresholds:
      batch_duration_warn: 1.5          # 批次耗时告警阈值(秒)
      memory_increase_warn: 256         # 内存增长告警阈值(MB)
```

**指标类型**:

- `duration`: 耗时统计
- `memory`: 内存使用
- `cpu`: CPU 使用

#### 3.7.3 关联可观测性 (relations)

```yaml
observability:
  relations:
    enabled: true
    sampling_rate: 0.05          # 采样率(0.0-1.0)
    log_type_mismatch: true      # 记录类型不匹配日志
    max_samples: 500             # 最大采样数量
    report:
      format: json               # 报告格式:console/json/none
      output: ./output/relations_report.json
```

#### 3.7.4 可视化输出 (viz)

```yaml
observability:
  viz:
    enabled: true
    output_dir: ./output         # 输出目录(自动追加 scalim-viz)
    trace_enabled: false         # 是否输出 viz_trace.jsonl(高频 trace)
    append: false                # 显式 output_path/snapshot_path 时是否追加(默认覆盖避免跨 run 混写)
    payload_policy: summary      # payload 策略:none/summary/sample/full
    sample_size: 5               # sample 策略下的样本数量
    run_name: order_report       # 运行名称
    env: production              # 环境标签
```

#### 3.7.5 执行追踪 (trace)

```yaml
observability:
  trace:
    enabled: true    # 启用执行追踪(记录批次级执行步骤)
```

#### 3.7.6 行缺口统计 (row_gap)

```yaml
observability:
  row_gap:
    enabled: true
    primary_loader_name: primary_keys
    data_loader_names: [base_info, detail_info]
    sample_limit: 5               # 缺口采样数量
```

#### 3.7.7 内存优化统计 (memory_opt)

```yaml
observability:
  memory_opt:
    enabled: true
    auto_report: true
    max_fields: 0                 # 摘要字段上限(0 表示不限制)
```

#### 3.7.8 静默与性能建议 (fastpath)

Scalim 默认**静默**:不会自动注册 logging observer,也不会输出执行进度日志.需要日志时请显式启用 `observability.logging.enabled: true`.

- 未启用任何 hook/observer 时,事件分发会走 wants=false 的 fastpath 直接短路,避免构建事件对象/进入锁区/准备高成本 payload.
- 仅启用你需要的观测插件(例如仅在排障时开启 `trace`/`viz`/`performance`),并避免订阅高频事件(如 `field_compute`/`loader_call`).
- 如需采样/摘要以降低开销,优先选择插件的 `payload_policy`/`sample_size` 等策略,而不是在热路径里做额外计算.

---

## 4. 高级特性 (Advanced Features)

### 4.1 YAML 锚点与模板复用

使用 YAML 锚点(`&`)和别名(`*`)复用配置:

```yaml
_templates:
  # 定义可复用的配置
  common_field: &common_field
    name: 默认名称
    value_cast: auto

  step_to_customers: &step_to_customers
    from: orders.customer_id
    to: customers.customer_id

  params_keys: &params_keys
    ids: {$keys: {as: set}}

relations:
  orders_to_customers:
    steps:
      - *step_to_customers

sources:
  customers:
    params: *params_keys

  products:
    params: *params_keys
```

**合并配置**:

```yaml
_templates:
  base_step: &base_step
    from: orders.customer_id
    to: customers.customer_id

relations:
  orders_to_customers_default:
    steps:
      - *base_step

  orders_to_customers_custom:
    steps:
      - <<: *base_step            # 继承 base_step
        lookup_cast:              # 添加自定义属性
          name: int
```

### 4.2 params 模板指令详解

#### 4.2.1 `$keys`: 注入 lookup keys

`$keys` 会把当前 ref lookup 的 keys 注入到模板指定位置(支持 nested/list 位置):

```yaml
sources:
  customers:
    loader: "myapp.loaders:load_customers"
    key: customer_id
    params:
      customer_ids_set: {$keys: {as: set}}
```

**对应的 Loader 函数签名**:

```python
def load_customers(customer_ids_set: set[int]) -> dict:
    pass
```

> NOTE: `$keys.as=list` 的顺序仅保证“同一输入下稳定可重复”.由于 keys 在框架内部通常先去重为集合,因此 list 顺序是框架的 canonical 顺序,
> 并不承诺与输入行的出现顺序一致.如果 loader 需要特定排序,请在 loader 内自行排序/归并.

#### 4.2.2 `$rows`: 注入 batch rows

`$rows` 会把当前批次的行上下文(batch rows)注入到模板指定位置:

```yaml
sources:
  customers:
    loader: "myapp.loaders:load_customers_by_rows"
    key: customer_id
    params:
      rows: {$rows: {cache_mode: batch}}
```

**对应的 Loader 函数签名**:

```python
def load_customers_by_rows(rows: list[dict]) -> dict:
    pass
```

> 注意: `$rows` 会触发 rows barrier.在 `parallel_mode="adaptive"` 下,该层 LoadRef 会按串行执行.

### 4.3 键值归一化 (lookup_cast)

#### 4.3.1 auto: 自动归一化

```yaml
lookup_cast:
  name: auto        # 自动推断类型并归一化
```

#### 4.3.2 int/str: 类型转换

```yaml
lookup_cast:
  name: int         # 转为整数

lookup_cast:
  name: str         # 转为字符串
```

#### 4.3.3 sep_first: CSV 首值截取

处理逗号分隔的多值字段,取第一个值:

```yaml
# 假设 orders.small_group_ids = "1,2,3"
relations:
  orders_to_small_groups:
    steps:
      - from: orders.small_group_ids
        to: small_groups.small_group_id
        lookup_cast:
          name: sep_first
          sep: ","        # 按逗号分割,取 "1"
```

### 4.4 缓存策略 (cache_mode)

#### 4.4.1 none: 不缓存

```yaml
sources:
  customers:
    cache_mode: none        # 每次关联都重新查询
    params:
      ids: {$keys: {as: set}}
```

提示:

- ref loader 通常需要在 `params` 模板中显式使用 `$keys` 或 `$rows`,否则 loader 不会收到 lookup 上下文,可能只能全量加载.

#### 4.4.2 preload_forever: 预加载永久缓存

```yaml
sources:
  order_types:
    cache_mode: preload_forever    # 启动时加载一次,永久缓存
    params:
      group_by: type_id
```

提示:

- `preload_forever` 场景允许声明 `params`.当 `params` 非空时,预加载调用会透传 kwargs;为空则保持零参 preload.
- `preload_forever` 场景禁止在 `params` 中使用 `$keys/$rows`.

### 4.5 多输出编排与派生汇总 (outputs / output_composition)

`YAML DSL` 支持在顶层通过 `outputs` 声明多输出编排(同 workbook 多 sheet / where 分发 / aggregate 派生汇总 / meta/audit),
运行时会将其编译为执行层的 `ExecutionRequest.output_composition`.

关键点:

- `outputs` 是有序列表;顺序决定 primary 输出
- 当多个 outputs 共享同一 Excel `path` 时,每个 output 必须显式设置 `sheet`(否则会覆盖同一个 sheet)
- Python 调用侧可通过 `overrides.outputs` **整体替换** YAML 的 `outputs`(replace).优先级: `overrides.outputs` > YAML `outputs` > 默认(不写文件;仅 sink 保留数据)
- `overrides.outputs` 必须为非空 list;本版本仅承诺明细输出(detail)最小子集: `name/container/fields`(不支持 `where/from/aggregate`)
- 若 `overrides.outputs` 把原本的 workbook outputs 替换成纯 `csv` 等非 workbook 输出,则未显式设置 `path` 的
  `meta/audit` 不再继承原 YAML 的 workbook,而是会被跳过;若仍需输出这些 extra sheets,请显式配置 `meta.path`
  / `audit.path`

#### 4.5.1 示例: YAML 声明多 sheet(明细 + 汇总 + meta + audit)

```yaml
outputs:
  - name: detail
    container: {type: workbook, path: ./output/report.xlsx, sheet: 明细}
    fields: [order_id, order_source, amount, cost, profit]
  - name: summary
    container: {type: workbook, path: ./output/report.xlsx, sheet: 汇总}
    aggregate:
      group_by: [order_source]
      fields:
        order_cnt: {count: {field: order_id}}
        sum_amount: {sum: {field: amount}}
        sum_profit: {sum: {field: profit}}
meta: true
audit: true
```

#### 4.5.2 示例: Python 运行期覆盖 outputs(动态选字段/路径/sheet)

```python
from scalim.dsl.by_yaml import RunOverrides, run

result = run(
    "path/to/config.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
    overrides=RunOverrides(
        outputs=[
            {
                "name": "detail",
                "container": {"type": "workbook", "path": "./output/report.xlsx", "sheet": "明细"},
                "fields": ["order_id", "amount", "profit"],
            }
        ]
    ),
)
```

### 4.6 下游集成工具(稳定入口): `scalim.dsl.by_yaml.tools`

下游在做集成时,常见还需要一些“工具/自省”能力(例如读取输出字段配置、推导相对引用的基准模块路径).这类能力请优先使用稳定工具面:

- `scalim.dsl.by_yaml.tools.load_output_config(yaml_path)`
  - 返回 `dict`(运行期)且至少包含 keys: `params` / `field_name_mapping` / `output_fields` / `outputs`
- `scalim.dsl.by_yaml.tools.derive_base_module_path(yaml_path, sys_path=..., cwd=...)`
  - 根据 `yaml_path + sys.path` 推导相对引用的 `base_module_path`

迁移提示:

- 若你之前直接从 YAML DSL 的内部实现子包(例如 `runtime` 子包)导入这些 helper,请统一迁移到 `scalim.dsl.by_yaml.tools`

最小示例:

```python
from scalim.dsl.by_yaml.tools import derive_base_module_path, load_output_config

cfg = load_output_config("path/to/config.yaml")
base_module_path = derive_base_module_path("path/to/config.yaml")
```

---

## 5. 完整示例 (Complete Examples)

### 5.1 示例1: 订单报表(简单关联)

**场景**:生成包含客户信息、支付方式、国家信息的订单报表.

**配置文件**:

```yaml
name: order_report
description: 订单报表 - 展示客户、支付、国家等关联信息

batch_size: 3

main_source:
  source_id: orders
  loader: "scalim_misc.example_report_ir:DAL.paged_get_order_list"
  params:
    begin_time: "2024-01-01"
    end_time: "2024-01-07"
  fields:
    order_id:
      name: 订单ID

    amount:
      name: 金额

    cost:
      name: 成本

    customer_id:
      name: 客户ID

    pay_id:
      name: 支付ID

relations:
  orders_to_customers:
    steps:
      - from: orders.customer_id
        to: customers.customer_id

  orders_to_pays:
    steps:
      - from: orders.pay_id
        to: pays.pay_id

sources:
  customers:
    loader: "scalim_misc.example_report_ir:BLL.get_customer_info_from_api_of_kw_params"
    key: customer_id
    params:
      customer_ids_set: {$keys: {as: set}}
    fields:
      customer_name:
        name: 客户名称
        relation: *orders_to_customers

  pays:
    loader: "scalim_misc.example_report_ir:BLL.get_pay_info_from_api_of_concrete_params"
    key: pay_id
    params:
      pay_ids_set: {$keys: {as: set}}
    fields:
      pay_method:
        name: 支付方式
        relation: *orders_to_pays

fields:
  profit:
    name: 利润
    compute: "amount - cost"

  profit_margin:
    name: 利润率
    compute: "(amount - cost) / amount * 100 if amount > 0 else 0"

outputs:
  - name: detail
    container: {type: csv, path: ./.tmp/output/order_report.csv}
    fields: [order_id, customer_name, amount, cost, profit]
```

### 5.2 示例2: 电商报表(多级关联、复合键、派生字段)

**场景**:生成包含多级关联、复合键关联、派生字段的电商订单报表.

**配置文件**(简化版):

```yaml
name: ecommerce_order_report
description: 电商订单报表

batch_size: 100

_templates:
  step_orders_to_customers: &step_orders_to_customers
    from: orders.customer_id
    to: customers.customer_id

  step_orders_to_products: &step_orders_to_products
    from: orders.product_id
    to: products.product_id

main_source:
  source_id: orders
  loader: "scalim_misc.demo_big_data_report.loaders:load_orders"
  params:
    field_keys:
      - order_id
      - order_date
      - quantity
      - unit_price
      - discount_rate
      - customer_id
      - product_id
  fields:
    order_id:
      name: 订单ID

    quantity:
      name: 数量
      value_cast: int

    unit_price:
      name: 单价

    discount_rate:
      name: 折扣率

relations:
  orders_to_customers:
    steps:
      - *step_orders_to_customers

  orders_to_categories:  # 多级关联
    steps:
      - *step_orders_to_products
      - from: products.category_id
        to: categories.category_id

  orders_to_region_pricing:  # 复合键关联
    steps:
      - from: [orders.region_id, orders.product_category_id]
        to: [region_pricing.region_id, region_pricing.product_category_id]

sources:
  customers:
    loader: "scalim_misc.demo_big_data_report.loaders:load_customers"
    key: customer_id
    params:
      ids: {$keys: {as: set}}
    fields:
      customer_name:
        name: 客户姓名
        relation: *orders_to_customers

      customer_level:
        name: 会员等级
        relation: *orders_to_customers

  products:
    loader: "scalim_misc.demo_big_data_report.loaders:load_products"
    key: product_id
    lookup_cast:
      name: int
    params:
      ids: {$keys: {as: list}}
    fields:
      product_name:
        name: 产品名称
        relation: *orders_to_products

      product_category_id:
        name: 产品分类ID
        extract: category_id
        relation: *orders_to_products

  categories:
    loader: "scalim_misc.demo_big_data_report.loaders:load_categories"
    key: category_id
    params:
      ids: {$keys: {as: set}}
    fields:
      category_name:
        name: 产品分类
        relation: *orders_to_categories

  region_pricing:
    loader: "scalim_misc.demo_big_data_report.loaders:load_region_pricing"
    key: [region_id, product_category_id]
    cache_mode: preload_forever
    fields:
      price_adjustment:
        name: 价格调整系数
        relation: *orders_to_region_pricing

      shipping_fee:
        name: 运费
        relation: *orders_to_region_pricing

      tax_rate:
        name: 税率
        relation: *orders_to_region_pricing

fields:
  order_amount:
    name: 订单金额
    compute: "quantity * unit_price * discount_rate"

  profit:
    name: 利润
    compute: "order_amount - product_cost * quantity"

  tax_amount:
    name: 税费
    compute: "order_amount * tax_rate"

  final_price:
    name: 最终价格
    compute: "order_amount * price_adjustment + shipping_fee"

outputs:
  - name: detail
    container: {type: csv, path: ./.tmp/output/ecommerce_report.csv, header_fields_output_by: name}
    fields:
      - order_id
      - customer_name
      - quantity
      - unit_price
      - product_name
      - category_name
      - price_adjustment
      - shipping_fee
      - tax_rate
      - order_amount
      - profit
      - tax_amount
      - final_price

observability:
  performance:
    enabled: true
    metrics: [duration, memory, cpu]
    sampling_interval: 2
    report:
      format: csv
      output: ./.tmp/output/ecommerce_perf_report.csv
      include_details: true
    thresholds:
      batch_duration_warn: 1.5
      memory_increase_warn: 256
  relations:
    enabled: true
    sampling_rate: 0.05
    log_type_mismatch: true
    max_samples: 500
    report:
      format: json
      output: ./.tmp/output/ecommerce_relations_report.json
```

---

## 6. 最佳实践 (Best Practices)

### 6.1 字段命名规范

**source_id 和 field_id 命名**:

- 使用小写字母、数字和下划线
- 首字符必须是字母或下划线
- 使用蛇形命名法(snake_case)

```yaml
# 推荐
source_id: order_details
field_id: customer_name

# 不推荐
source_id: OrderDetails
field_id: customerName
```

### 6.2 YAML 锚点复用技巧

**组织模板区域**:

```yaml
_templates:
  # 关系步骤模板
  steps:
    to_customer: &step_to_customer
      from: orders.customer_id
      to: customers.customer_id

    to_product: &step_to_product
      from: orders.product_id
      to: products.product_id

  # params 模板片段
  params:
    keys_set: &params_keys_set
      ids: {$keys: {as: set}}

    keys_list: &params_keys_list
      ids: {$keys: {as: list}}

  # 字段配置模板
  fields:
    customer_name: &field_customer_name
      name: 客户姓名
      relation: *step_to_customer

# 使用模板
relations:
  orders_to_customers:
    steps:
      - *step_to_customer

sources:
  customers:
    params: *params_keys_set
    fields:
      customer_name: *field_customer_name

  products:
    params: *params_keys_list
```

### 6.3 性能优化建议

**1. 合理设置 batch_size**:

```yaml
# 小数据集或低内存环境
batch_size: 500

# 大数据集或高内存环境
batch_size: 2000
```

**2. 使用缓存**:

```yaml
sources:
  # 维度表(数据量小且不变)使用 preload_forever
  order_types:
    cache_mode: preload_forever

  # 事实表(数据量大)使用 none
  orders:
    cache_mode: none
```

**3. 启用流式输出**:

```yaml
outputs:
  - name: detail
    container: {type: csv, path: ./output/report.csv, streaming: true} # streaming=true(按行写出;减少内存占用)
    fields: [order_id]
```

**4. 使用 `$keys` 而非 `$rows`(尽量避免 rows barrier)**:

```yaml
# 推荐:`$keys`
sources:
  customers:
    params:
      ids: {$keys: {as: set}}

# 谨慎使用:`$rows`(可能传递大量数据,并触发 rows barrier)
sources:
  customers:
    params:
      rows: {$rows: {cache_mode: batch}}
```

### 6.4 安全注意事项

**1. 避免在配置中硬编码敏感信息**:

```yaml
# 不推荐
main_source:
  params:
    api_key: "sk-xxxxx"

# 推荐:由调用方或 loader 在运行时注入(Scalim 不会自动做 `${...}` 插值)
main_source:
  params:
    api_key: null
```

示例:在 loader 内读取环境变量(推荐):

```python
import os

def load_orders(*, api_key=None, **kwargs):
    api_key = api_key or os.environ["API_KEY"]
    ...
```

**2. Allowlist(强烈推荐)**:

YAML 中的 `loader` / `call_by` 允许引用 Python 可调用对象,属于动态执行边界.在生产/低信任输入场景 MUST 使用 allowlist 限制可解析的引用:

```python
from scalim.dsl.by_yaml import run

# 模块级 allowlist(允许该模块及其子模块)
run(
    "path/to/config.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
)

# 函数级 allowlist(更精确,推荐)
run(
    "path/to/config.yaml",
    allowed_functions=frozenset(
        [
            "myapp.loaders:load_orders",
            "myapp.loaders:load_customers",
        ]
    ),
)
```

- `allowed_modules`: 粗粒度,适合把 loader 统一收敛到单一模块(如 `myapp.loaders`)
- `allowed_functions`: 细粒度,推荐在生产使用;支持 `module:function` 与 `module.function` 两种写法
- wildcard `*` 默认被禁止(避免误用导致 allowlist 形同虚设);仅在 `resolver_trusted_mode=trusted_allow_all_modules` 下允许显式放宽

**reference 形式与注意事项**:

- dotted-style: `module.path.function`
- class-style: `module.path:function` / `module.path:obj.method`
- 相对 module 引用: 以 `.` / `..` 开头(相对 YAML 文件所在目录对应模块路径),例如 `.loaders:load_orders` / `..common.transforms:fixup`
- 相对引用会先归一化为绝对引用再做 allowlist 校验;因此 allowlist 需要覆盖归一化后的模块前缀
- `allowed_functions` 对 class-style 支持**完整链匹配**(例如允许 `pkg.mod:Obj.safe` 时,`pkg.mod:Obj.unsafe` 会被拒绝;同时也支持等价 dotted 形式 `pkg.mod.Obj.safe`)
- `allowed_modules` 仍是模块级放行(允许模块及其子模块内的所有可调用引用);如需更严格限制,优先使用 `allowed_functions`

相对引用示例(假设 `config.yaml` 位于 `myapp/reports/config.yaml`,且 `myapp` 在 `PYTHONPATH` / `sys.path` 可导入范围内):

```yaml
main_source:
  source_id: orders
  loader: ".loaders:load_orders"  # => myapp.reports.loaders:load_orders
```

**高级用法(迁移提示)**:

- 旧代码如果绕过官方 facade 直接调用内部编译器/转换器,建议迁移到 `scalim.dsl.by_yaml.compile/run`,并显式配置 allowlist:

```python
from scalim.dsl.by_yaml import ResolverTrustedMode, compile

# 推荐:显式 allowlist(安全默认)
_ = compile(
    "path/to/config.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
)

# 仅用于可信环境/测试:显式启用 trusted-mode 放宽为允许任意模块(不推荐生产使用)
_ = compile(
    "path/to/config.yaml",
    allowed_modules=frozenset(["*"]),
    resolver_trusted_mode=ResolverTrustedMode.TRUSTED_ALLOW_ALL_MODULES,
)
```

**3. compute / call_by 的边界**:

- `compute` 使用受限 AST 表达式引擎(禁止 attribute/subscript/dunder 等逃逸),并默认启用**资源上限**来阻断配置构造型 DoS(如表达式过长、AST 过大/过深、过大的常量字面量、repeat/range 等)
- `compute` 不支持方法调用/attribute call(例如 `.get()` / `.strip()`),遇到此类需求推荐改用 `call_by` 迁移到 Python 函数(同样受 reference + allowlist 约束):

```yaml
fields:
  # ❌ 不被允许: method call
  city:
    compute: "address.get('city', '')"

  # ✅ 推荐: call_by
  city:
    call_by: "myapp.transforms:dict_get(mapping=address, key='city', default='')"
```
- `call_by` 可将复杂逻辑移到 Python 函数,但同样走 reference + allowlist.建议将可执行函数收敛到受控模块并使用函数级 allowlist 精确放行.

**compute limits(可选覆盖)**:

compute limits 等更细粒度安全配置属于内部实现细节;如确需自定义,请以 OpenSpec 与源码为准:

- `src/scalim/dsl/by_yaml/config_parsing/security.py`

常见报错关键字(触发上限时会出现在错误信息中):
`max_expression_len` / `max_ast_nodes` / `max_ast_depth` / `max_literal_string_len` / `max_collection_literal_len` / `max_repeat` / `max_range_len`

**4. 验证用户输入**:

- 在 loader 函数中验证参数
- 防止 SQL 注入、路径遍历等攻击

---

## 7. 常见问题 (FAQ)

### Q1: 如何调试关联关系？

**A**: 启用关联可观测性:

```yaml
observability:
  relations:
    enabled: true
    sampling_rate: 1.0          # 采样率 100%
    log_type_mismatch: true
    report:
      format: json
      output: ./debug_relations.json
```

### Q2: 派生字段依赖其他派生字段怎么办？

**A**: 直接在 `compute` 中引用其它派生字段的 `field_id` 即可,系统会从表达式推导依赖并按拓扑顺序计算(无需 `depends_on`):

```yaml
fields:
  order_amount:
    name: 订单金额
    compute: "quantity * unit_price"

  tax_amount:
    name: 税费
    compute: "order_amount * tax_rate"
```

### Q3: 不同 source 下 field_id 重名怎么办？

**A**: `field_id` 必须全局唯一.请在 YAML 中重命名这些字段(用 `extract` 指向真实 data_key),例如:

```yaml
sources:
  customers:
    fields:
      customer_name:
        extract: name
        name: 客户名称

  products:
    fields:
      product_name:
        extract: name
        name: 产品名称
```

然后在 `outputs.*.fields` 中直接使用 `customer_name` / `product_name`.

### Q4: lookup_cast 和 value_cast 有什么区别？

**A**:

- `lookup_cast`: 在关联前对**键值**进行归一化(用于 `from` 侧)
- `value_cast`: 在写入上下文/输出前对**字段值**进行转换(用于源字段)

```yaml
# lookup_cast: 关联时转换
relations:
  orders_to_customers:
    steps:
      - from: orders.customer_id
        to: customers.customer_id
        lookup_cast:
          name: int    # 确保 orders.customer_id 是整数

# value_cast: 输出时转换
main_source:
  fields:
    amount:
      value_cast: decimal    # 金融/金额类字段推荐: 用 Decimal 避免 float 精度问题
```

### Q5: 何时使用 preload_forever 缓存？

**A**:

- **适用场景**:维度表、配置表(数据量小且不常变化)
- **不适用场景**:事实表、大数据量表

```yaml
sources:
  # 适用:订单类型(数据量小)
  order_types:
    cache_mode: preload_forever

  # 不适用:订单明细(数据量大)
  order_details:
    cache_mode: none
```

### Q6: 如何优化内存占用？

**A**:

1. **减小 batch_size**:

```yaml
batch_size: 500    # 默认 1000
```

2. **启用流式输出**:

```yaml
outputs:
  - name: detail
    container: {type: csv, path: ./output/report.csv, streaming: true}
    fields: [order_id]
```

3. **优先使用 `$keys`(而不是 `$rows`)**:

```yaml
sources:
  customers:
    params:
      ids: {$keys: {as: set}}
```

4. **启用内存优化统计**:

```yaml
observability:
  memory_opt:
    enabled: true
    auto_report: true
```

### Q7: 如何生成 JSON Schema？

**A**:

- 查看/导出 schema: `scalim-cli yaml-dsl schema show` / `scalim-cli yaml-dsl schema path`
- 更新仓库内 schema 生成物: `just gen-yaml-dsl-schema` (并提交 `src/scalim/dsl/by_yaml/schema/demand.gen.json`)

### Q8: 如何验证配置文件？

**A**:

- CLI 校验参数与更多命令见: `scalim-cli yaml-dsl validate --help`

```bash
# 使用 CLI 验证
scalim-cli yaml-dsl validate config.yaml
```

```python
# 或在代码中(编译时会自动校验;需配置 allowlist)
from scalim.dsl.by_yaml import compile
_ = compile("config.yaml", allowed_modules=frozenset(["myapp.loaders"]))
```

### Q9: 支持哪些输出格式？

**A**:

- **CSV**: `outputs.*.container.type: csv`
- **Excel(workbook)**: `outputs.*.container.type: workbook`(需要 `openpyxl` 依赖)

```yaml
outputs:
  - name: detail
    container: {type: workbook, path: ./output/report.xlsx, sheet: 明细}
    fields: [order_id]
```

### Q10: 如何在 Python 中调用 YAML DSL？

**A**:

```python
from scalim.dsl.by_yaml import run
from scalim.hooks.base import BaseHook


class _MyHook(BaseHook):
    def on_pipeline_end(self, event) -> None:  # type: ignore[override]
        _ = event


# 执行配置
result = run(
    "path/to/config.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
    components=[_MyHook()],  # (可选) 附加自定义 hook/observer 组件
)

# 访问结果
print(f"处理行数: {result.total_rows}")
print(f"输出路径: {result.output_path}")
```

#### (可选)YAML 模板预编译: `template_vars`

当你需要在 YAML **文本层**使用 `{{ ... }}` / `{% ... %}` 模板语法时(例如未加引号的占位符、条件/循环生成片段),可以在 Python 入口传入 `template_vars`。系统会在 **YAML parse 前**先渲染文本,再进入正常的 parse + 校验/编译流程。

注意:

- `template_vars` 不是 YAML schema 字段;`scalim-cli yaml-dsl validate/schema validate` 当前也不支持注入 `template_vars`。
- 能用结构化注入时,优先用 `init_vars` + `{$init_var: <name>}`(CLI 可直接校验;也更稳定/可维护)。

```python
result = run(
    "path/to/config.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
    template_vars={"output_path": "./out/report.csv"},
)
```

---

## 附录

### A. 完整配置示例位置

- **简单订单报表**: `tests/fixtures/order_report.yaml`
- **电商报表(完整)**: `artifacts/skills/scalim-yaml-dsl/references/generated/example-full/ecommerce_report.gen.yaml`

### B. 相关文档

- [架构详解](../architecture/arch.md)
- [Benchmark 指南](../benchmark/guide.md)
- [可视化工具(Scalim Viz)](../viz/scalim-viz.md)
- [YAML DSL Schema Meta 参考](schema-meta.md)
