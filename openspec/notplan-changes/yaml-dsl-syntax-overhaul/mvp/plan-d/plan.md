# Plan D: Type-tagged arrays (everything has an explicit `id`)

## One-liner

把“YAML 映射 key 当作 id”的模式改为“所有对象显式 `id` 字段 + 数组承载”,让 patch/merge/生成更稳定,同时减少对象身份(alias)依赖。

## Why consider this

- 映射键作为 id 的模式对 human 很友好,但对:
  - schema 生成与 editor 自动补全
  - 多处引用(ref)的一致性校验
  - 未来做自动重写/格式化/补全
  都会引入“隐式语义”成本
- 数组 + 显式 id 更接近“AST”,有利于工具链与确定性输出

## Proposed shape (schema-level)

```yaml
name: <str>

sources:
  - id: <source_id>
    main: <bool?>
    loader: <python-ref>
    key: <str|[str,...]?>          # optional for main
    params: <template>
    fields:
      - id: <field_id>
        name: <str?>
        extract: <path?>?
        value_cast: <enum?>?
        via: <join_id?>?

joins:
  - id: <join_id>
    steps:
      - from: <source.field>
        to: <source.field>

derive:
  - id: <field_id>
    name: <str?>
    expr: <compute-expr> | call: {...}

output:
  format/path/streaming/...
  select:
    - ref: <field-ref>
      name: <override?>
```

## Pros / Cons

Pros:
- 引用/补全/静态校验更稳定(显式 id)
- 对“自动升级器/格式化器/生成器”更友好

Cons:
- 对人手写更啰嗦(每个对象都要写 `id`)
- 读起来不如映射直观(尤其是 fields/sources 很长时)

