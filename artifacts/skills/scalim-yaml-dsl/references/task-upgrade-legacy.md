# Upgrade Legacy YAML

## 何时读取

- 用户明确说“升级旧 YAML DSL”
- `validate` / `schema validate` 提示 legacy field
- 你看到旧版 `bind`、旧顶层结构、旧输出字段写法

## 原则

- 直接升级到当前写法
- 不保留兼容层
- 升级后立刻跑 `schema validate` 与 `validate`

## 必查项目

### 1. legacy 字段

以下字段不再允许出现在当前结构:

- `relations_sql_like`
- `relations_graph`
- `foreign_key`
- `target`
- `from`
- `via`
- `column`
- `pk`
- `pk_transform`
- `derived`
- `key_transform`
- `primary`

### 2. 顶层 `fields`

- 顶层 `fields` 只允许派生字段
- 如果顶层字段里出现 `field: xxx`,说明还是旧思路,需要移到 `main_source.fields` 或 `sources.<id>.fields`

### 3. `bind` / `to_bind`

旧写法:

```yaml
bind:
  param: ids
```

新写法:

```yaml
bind:
  use_keys:
    param: ids
```

`rows` 模式则改成:

```yaml
to_bind:
  use_rows:
    param: rows
    cache_mode: batch
```

### 4. `output.fields`

旧写法:

```yaml
output:
  fields:
    - order_id
    - customer_name
```

新写法:

```yaml
output:
  fields:
    - field_id: order_id
    - field_id: customer_name
```

或直接用 alias:

```yaml
output:
  fields:
    - *order_id
    - *customer_name
```

### 5. relation 引用

- `relation` 不要写字符串 relation_id
- 用 YAML alias 或内联 `steps`

### 6. step 字段选择

- `steps.from` / `steps.to` 使用 `field_id`
- 即使 loader 真实列名不同,这里仍然写 YAML key

## 升级顺序

1. 清掉 legacy 字段
2. 规范化 `main_source` / `sources` / 顶层 `fields`
3. 把所有 `bind` / `to_bind` 改成 `use_keys` / `use_rows`
4. 重写 `output.fields`
5. 检查 relation steps 是否还在写 `data_key`
6. 跑校验并修掉剩余错误

## 最小自检

```bash
uv run scalim-cli yaml-dsl schema validate <file.yaml> --strict
uv run scalim-cli yaml-dsl validate <file.yaml> --strict
```

## 常见报错到修复动作

- `Legacy field 'xxx' is not allowed in v3`
  - 删除旧字段,改写到当前入口结构
- `v3 fields 'xxx' only allow derived fields`
  - 把该字段移回源字段容器
- `output.fields[0] must be explicit field object`
  - 把字符串改成 alias 或显式对象
- `Unknown field`
  - 先查 typo,再查是否仍在使用旧字段名

需要完整字段与 schema 细节时再读:

- [syntax-catalog.gen.md](syntax-catalog.gen.md)
