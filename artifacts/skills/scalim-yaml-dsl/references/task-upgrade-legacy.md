# Upgrade Legacy YAML

## 何时读取

- 用户明确说“升级旧 YAML DSL”
- `validate` / `schema validate` 提示 legacy field
- 你看到旧版 `bind` / `to_bind`、旧顶层结构、旧输出字段写法

## 原则

- 直接升级到当前写法
- 不保留兼容层
- 升级后立刻跑 `schema validate` 与 `validate`

## YAML DSL 升级批次索引 (自动生成)

<!-- BEGIN AUTOGEN:yaml-dsl-upgrades -->
- 2026-03-10: yaml-field-extract
  - Docs: `docs/doc/yaml-dsl/upgrades/2026-03-10-yaml-field-extract.md`
  - OpenSpec: `openspec/changes/archive/2026-03-10-yaml-field-extract/`
  - Spec: `openspec/specs/yaml-field-extract/spec.md`
- 2026-03-10: yaml-source-normalize
  - Docs: `docs/doc/yaml-dsl/upgrades/2026-03-10-yaml-source-normalize.md`
  - OpenSpec: `openspec/changes/archive/2026-03-10-yaml-source-normalize/`
  - Spec: `openspec/specs/demand-dsl/spec.md`
- 2026-03-11: yaml-params-template
  - Docs: `docs/doc/yaml-dsl/upgrades/2026-03-11-yaml-params-template.md`
  - OpenSpec: `openspec/changes/archive/2026-03-11-yaml-inline-dynamic-params/`
  - Spec: `openspec/specs/demand-dsl/spec.md`
<!-- END AUTOGEN:yaml-dsl-upgrades -->

## whole-result reshape: 用 `normalize`,不用字段级 `extract`

如果你的 lookup loader 返回 `list[row]`,而你过去通过 Python wrapper 把它改成 `key -> row` mapping,现在可以优先用 `sources.<id>.normalize.kind=index_by_key` 完成归一化.

边界:
- `normalize`: 对整个 source 返回值做一次 reshape(发生在字段读取前)
- `extract`: 从单条 row value 里取字段(包含 nested 取值与 rename)

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
- 如果顶层字段里出现源字段写法(例如 `extract:`/`relation:`/`value_cast:`),说明位置错,需要移到 `main_source.fields` 或 `sources.<id>.fields`

### 3. 源字段取值: `field` → `extract` (breaking)

旧写法(不再允许):

```yaml
main_source:
  fields:
    customer_id:
      field: customer_id_col
```

新写法:

```yaml
main_source:
  fields:
    customer_id:
      extract: customer_id_col
```

提示:

- `fields.*.field` 已从稳定 YAML authoring surface 移除,出现即 fail-fast
- `extract` 省略时,等价于 `extract: <field_id>`(顶层同名 key)

### 4. `bind` / `to_bind` -> `params` 模板指令(`$keys` / `$rows`)

旧写法(不再允许,会 fail-fast):

```yaml
bind:
  use_keys:
    param: ids
```

新写法(推荐):

```yaml
params:
  ids: {$keys: {as: set}}
```

`rows` 模式:

```yaml
params:
  rows: {$rows: {cache_mode: batch}}
```

提示:

- `$rows` 会触发 rows barrier.在 `parallel_mode="adaptive"` 下,该层 LoadRef 会按串行执行.
- `cache_mode: preload_forever` 的 source 禁止在 `params` 中使用 `$keys/$rows`.

### 5. `output.fields`

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

### 6. relation 引用

- `relation` 不要写字符串 relation_id
- 用 YAML alias 或内联 `steps`

### 7. step 字段选择

- `steps.from` / `steps.to` 使用 `field_id`
- 即使 loader 真实列名不同,这里仍然写 YAML key

## 升级顺序

1. 清掉 legacy 字段
2. 规范化 `main_source` / `sources` / 顶层 `fields`
3. 把 `fields.*.field` 全部升级为 `fields.*.extract`
4. 把所有 `bind` / `to_bind` 改成 `params` 模板中的 `$keys` / `$rows` 指令节点
5. 重写 `output.fields`
6. 检查 relation steps 是否还在写 `data_key`
7. 跑校验并修掉剩余错误

## 最小自检

```bash
uv run scalim-cli yaml-dsl schema validate <file.yaml> --strict
uv run scalim-cli yaml-dsl validate <file.yaml> --strict
```

## 常见报错到修复动作

- `Legacy field 'xxx' is not allowed`
  - 删除旧字段,改写到当前入口结构
- `Derived field 'xxx' must declare compute/call_by`
  - 如果它是源字段,请移回 `main_source.fields`/`sources.*.fields`;如果它是派生字段,请补 `compute` 或 `call_by`
- `output.fields[0] must be explicit field object`
  - 把字符串改成 alias 或显式对象
- `Unknown field`
  - 先查 typo,再查是否仍在使用旧字段名

需要完整字段与 schema 细节时再读:

- [syntax-catalog.gen.md](syntax-catalog.gen.md)
