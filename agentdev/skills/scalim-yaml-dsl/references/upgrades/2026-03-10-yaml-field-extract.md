# 2026-03-10: yaml-field-extract

## 变更摘要

这次升级把“源字段如何从 loader 返回的 row value 里取值”统一收敛到一个入口: `extract`。

- `main_source.fields.*` / `sources.*.fields.*` 中，历史 `field: ...` **不再允许**（出现即 fail-fast）
- `extract: <expr>` 成为**唯一**字段取值写法（包含 rename 与 nested 取值）
- `extract` 支持 `dot + bracket` 路径表达式，覆盖嵌套 dict、dotted literal key、int key 场景
- 明确 **不做** `"1" ↔ 1` 隐式 cast，避免歧义
- 明确 **不支持** list/tuple 下标（`[1]` 永远表示 key=1，而不是 list index）

llmanspec 归档变更（含 proposal/design/spec/tasks）:
- `llmanspec/changes/archive/2026-03-10-yaml-field-extract/`

对应主规范:
- `llmanspec/specs/yaml-field-extract/spec.md`

## 破坏性变更(Breaking)

### 1) 源字段移除 `field: ...`

影响范围:
- `main_source.fields.<field_id>.field`（不再允许）
- `sources.<id>.fields.<field_id>.field`（不再允许）

迁移要点:
- 以前用 `field` 做 rename（例如 `field: category_id`），现在改为 `extract: category_id`
- 如果过去 `field` 的值与 `field_id` 相同，可以直接删掉该行（因为默认 `extract` 回退到 `field_id`）

### 2) 不要混淆两种“field”

这次移除的是**源字段定义**里的 `field: ...`（历史写法）。

`output.fields` 条目里用于“按 data_key 选择源字段”的选择器 `{field: <data_key>}` **仍然存在**，不属于本次移除范围。

## 迁移步骤

### Step 0: 先跑校验定位问题

- `uv run scalim-cli yaml-dsl validate <file.yaml>`
- `uv run scalim-cli yaml-dsl schema validate <file.yaml>`

### Step 1: 把所有源字段的 `field:` 改为 `extract:`

旧写法（不再允许）:
```yaml
sources:
  products:
    fields:
      product_category_id:
        field: category_id
```

新写法:
```yaml
sources:
  products:
    fields:
      product_category_id:
        extract: category_id
```

如果只是“顶层同名取值”，`extract` 可省略:
```yaml
main_source:
  fields:
    order_id:
      name: 订单ID
```
等价于:
```yaml
main_source:
  fields:
    order_id:
      extract: order_id
      name: 订单ID
```

### Step 2: 遇到嵌套结构，用 dot path

```yaml
sources:
  clearn_reasons:
    fields:
      review_status:
        extract: review_status
      customer_level:
        extract: CustomerMark.clearn_reason_level
```

注意：`extract` 起点是“当前 key 对应的 row value”。如果 row value 里有包裹层 `payload`，必须显式写出来:
```yaml
extract: payload.CustomerMark.clearn_reason_level
```

### Step 3: 遇到 int key，用 bracket int segment（建议总是写成字符串）

```yaml
sources:
  clearn_reasons:
    fields:
      customer_clearn_reason_level:
        extract: "[1].clearn_reason_level"
      operation_clearn_reason_level:
        extract: "[2].clearn_reason_level"
```

### Step 4: 遇到 dotted literal key，用 bracket string segment

```yaml
main_source:
  fields:
    dotted_x:
      extract: '["a.b"].x'
```

### Step 5: 明确区分 `"1"` 与 `1`

```yaml
main_source:
  fields:
    int_key_x:
      extract: "[1].x"      # key 是 int 1
    str_key_x:
      extract: '["1"].x'    # key 是 string "1"
```

### Step 6: list/tuple 下标不支持

即使中间值是 list，`[1]` 也不会索引它:
```yaml
extract: "[1].x"  # 不会当成 list index
```

如果确实需要 list index 语义，建议：
- 让 loader 直接返回更易消费的 mapping 结构；或
- 保留/新增一个最薄的 Python wrapper 先把 list 投影成 mapping/扁平字段，再用 `extract` 读取。

## 行为与边界

- 缺失任一 segment（中间为 None、key 不存在、属性不存在、`__getitem__` 不可用）→ 返回 `None`
- 非法表达式在编译/校验阶段 fail-fast（例如 `a..b`、`[-1]`、`[ 1 ]`、非法转义）
- 不做 `"1"` ↔ `1` 的隐式转换

如果你希望“缺失即报错”，请配合 guardrails 的 required-fields 能力（而不是把取值语法做得更复杂）。

## 常见报错与修复

- 出现 `field: ...`：
  - 报错类似：`Legacy source field 'field: ...' is not allowed; 请改用 'extract: ...'`
  - 修复：把 `field` 改成 `extract`（或删除以使用默认值）
- `extract` 写错（括号/引号/转义/连续点等）：
  - 报错会带字段路径与具体原因
  - 修复：优先把 bracket 段写成字符串形式，例如 `extract: "[1].x"`、`extract: '["a.b"].x'`
