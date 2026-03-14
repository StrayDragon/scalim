# 2026-03-14: yaml-dsl-output-fields-alias

## 变更摘要

本批次增强 `outputs.*.fields` 的 authoring surface,允许通过 YAML anchors/aliases 复用字段对象或字段列表,减少重复维护点:

- `outputs.*.fields` 的条目允许为 `field_id` 字符串(保持现有写法不变)
- `outputs.*.fields` 的条目允许为 YAML alias(object): 直接引用“已定义字段对象”(展开后为 dict),解析器会将其推导为对应的 `field_id`
- `outputs.*.fields` 支持 YAML alias(list) 与嵌套列表: 会递归展开/flatten,最终归一化为 `field_id` 字符串列表

OpenSpec 归档变更（含 proposal/design/spec/tasks）:
- `openspec/changes/archive/2026-03-14-yaml-dsl-output-fields-alias/`

对应主规范(节选):
- `openspec/specs/yaml-dsl-schema/spec.md`
- `openspec/specs/yaml-dsl-cli-validation/spec.md`

## 新语法要点

`outputs.*.fields` 的每一项现在允许为:

- `field_id` string: `- "order_id"`
- YAML alias(object): `- *quantity`(其中 `&quantity` 是字段定义对象)
- YAML alias(list) 或嵌套 list: `- *detail_fields` / `fields: [*detail_fields, extra_field]` (会被递归 flatten)

## 示例

### 1) alias(object): 复用字段定义对象以推导 `field_id`

```yaml
main_source:
  fields:
    quantity: &quantity {extract: quantity, name: 数量}

outputs:
  - name: detail
    container: {type: csv, path: ./out.csv}
    fields:
      - *quantity
      - "order_id"
```

其中 `*quantity` 展开后为 dict,解析器会基于 alias identity 优先匹配,并推导得到 `field_id="quantity"`.

### 2) alias(list): 复用字段列表(会 flatten)

```yaml
_templates:
  detail_fields: &detail_fields [order_id, quantity, final_price]

outputs:
  - name: detail
    container: {type: csv, path: ./out.csv}
    fields: *detail_fields

  - name: detail_plus
    container: {type: csv, path: ./out_plus.csv}
    fields:
      - *detail_fields
      - extra_field
```

## 注意事项

- YAML merge(`<<`) 可能产生新对象并丢失 alias identity;当 identity 反查失败时仅允许“唯一内容匹配”兜底. 若出现歧义/无法匹配,请改用字符串 `field_id`.
- 为减少 surprises,推荐优先使用显式 `field_id` 字符串;当字段很多/需要复用时再引入 alias。
