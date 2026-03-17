## 1. YAML 解析与 Schema

- [x] 1.1 扩展 `outputs.*.aggregate` 的字段引用: 支持 YAML alias 引用字段定义对象(list/object)并解析为 `field_id`(覆盖 group_by 与所有 `...: {field: ...}` / `...: {fields: [...]}` 位置)
- [x] 1.2 扩展 `outputs.*.aggregate` 的字段引用: 支持 YAML alias 引用 `aggregate.fields.<out_field_id>` 对象并解析为 `out_field_id`(覆盖 rank.by/order_by 与 score_by_rank.rank_field 等)
- [ ] 1.3 更新 JSON schema/hover: 上述位置允许 object/array(alias)写法,并说明“强合同建议显式写 fields,省略不保证顺序”
- [ ] 1.4 aggregate output 允许声明 `outputs.*.fields`(select + order)并更新 schema/hover: `fields` 来源范围= `aggregate.group_by` + `aggregate.fields` 的 key
- [ ] 1.5 aggregate.fields.<out_field_id> 支持可选 `name`(允许重复),并更新 schema/hover

## 2. 运行时编译与输出

- [ ] 2.1 derived output layout: 若声明 `outputs.*.fields` 则按其顺序导出;否则沿用默认 derived layout
- [ ] 2.2 `header_fields_output_by: name` 时,derived output 表头优先使用 `aggregate.fields.<out_field_id>.name`,缺省回退为 field_id

## 3. 测试与验收

- [ ] 3.1 增加 pytest 覆盖 alias 解析与 aggregate output fields/name 行为(SSOT: `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py`)
- [ ] 3.2 运行 `just qa` 验证(包含 drift gate: `just openspec-check` / schema validate / tests)
