## 1. Schema / Docs

- [x] 1.1 放宽 `outputs[*].fields` schema: items 支持 `string|object` (`schema_dsl.models.outputs.OutputTargetConfig`)
- [x] 1.2 运行 schema 生成并更新生成物(含 editor schema): `just gen-yaml-dsl-schema` + `just gen-yaml-dsl-editor-schema`
- [x] 1.3 更新 schema hover/示例: 展示 `- *alias` 与 `- "field_id"` 两种写法,并提示 merge 会丢失 identity

## 2. Runtime 解析

- [x] 2.1 更新 `config_parsing.parsers.outputs` 支持 fields 条目为 `str|dict`,并归一化为 `Tuple[str, ...]`
- [x] 2.2 实现 dict 条目 match 规则: identity(alias_index) 优先,identity 失败时做唯一 content match;歧义/找不到时 fail-fast
- [x] 2.3 错误信息改为可行动: 报错路径 `outputs.<i>.fields.<j>` + 候选 field_id + 建议改用 string field_id

## 3. Validator / CLI 体验

- [x] 3.1 在 `ConfigValidator.validate_report` 增加对 `outputs[*].fields` object 条目的语义校验(与运行时 match 规则一致)
- [x] 3.2 覆盖歧义/找不到/类型不对的诊断文本,确保 CLI `validate` 能附加正确位置并给出修复建议

## 4. Tests

- [x] 4.1 增加用例: `outputs[*].fields` 允许 `- *alias` 引用 main_source/source/derived 字段定义对象
- [x] 4.2 增加用例: identity 丢失时唯一 content match 通过
- [x] 4.3 增加用例: content match 歧义/找不到时 fail-fast,错误包含候选 field_id 与路径

## 5. QA

- [x] 5.1 运行 `just qa` 确认 lint/typecheck/tests + docs/schema drift gates 通过
