## Why

在近期的 YAML DSL `outputs` 语法升级后, `outputs[*].fields` 的条目目前被严格限制为 `field_id` 字符串列表.

但在旧配置/既有用法中,我们经常会在 `main_source.fields` / `sources.*.fields` 中为字段定义设置 YAML anchor,并在输出布局中通过 `*alias` 直接复用该字段定义对象,达到:

- 输出字段列表不需要重复写 `field_id` 字符串
- 在字段较多时减少 layout 与字段定义之间的“重复维护点”
- 通过 anchor 复用字段的 `name` / `value_cast` / `value_formatter` 等定义,让输出更稳定

目前该用法会因为 schema/validator 仅接受 string 而失败(条目为 dict),导致旧配置无法迁移,并且削弱 YAML DSL 的“可复用/可沉淀”优势.

此外,DSL 中已有类似场景(例如 `guardrails.loader.required_fields`)支持通过 YAML alias 引用字段定义对象,因此 `outputs[*].fields` 也应提供一致的 authoring surface.

## What Changes

- 扩展 `outputs[*].fields` 的条目类型,支持两种等价写法:
  - `field_id` 字符串(保持现有写法/行为不变)
  - YAML alias(对象)条目: 条目为某个字段定义 dict 的直接 alias(例如 `- *quantity`),解析器将其解析为对应的 `field_id`
- 解析器需要实现“match/反查”逻辑:
  - 优先使用“对象身份”(identity)反查: 通过 YAML alias 引用时, PyYAML 通常会复用同一份 dict 对象;系统应基于对象身份找到该 dict 对应的字段定义并得到 `field_id`
  - 兼容 PyYAML/处理中间步骤导致的对象非同一(identity 丢失)情况: 当对象身份反查失败时,系统应允许基于内容做匹配(仅当能唯一匹配到某个字段定义时才允许),否则给出明确错误并提示回退到字符串写法
- 更新 YAML DSL JSON Schema 与 hover 说明:
  - `outputs[*].fields.items` 从 `string` 扩展为 `anyOf: [string, object]`
  - 文档/hover 明确说明:
    - alias 条目用于“引用字段定义对象以得到 field_id”
    - YAML merge(`<<`) 可能产生新对象并丢失 alias 身份;此时建议使用字符串 `field_id`(或提供显式选择器,若未来支持)
- 增强 validator/CLI 诊断:
  - 当 `outputs[*].fields` 出现 object 条目且无法解析为唯一 `field_id` 时,校验 MUST 失败并给出更友好的可行动提示(例如候选字段列表/歧义原因/建议改用字符串 field_id)

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `yaml-dsl-schema`: `outputs[*].fields` 的 schema/hover 允许 alias(object) 条目.
- `yaml-dsl-cli-validation`: `PROJECT_CLI_NAME yaml-dsl validate` 对 `outputs[*].fields` 的 object 条目提供可行动的错误诊断.

## Impact

- 受影响模块(预期):
  - `src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py` + schema 生成物 `demand.gen.json`
  - `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py` (outputs 解析)
  - `src/scalim/dsl/by_yaml/config_parsing/validator.py` (schema/语义校验诊断质量)
- 测试/验收:
  - 增加 YAML fixtures 覆盖:
    - `outputs[*].fields` 使用 `- *alias` 引用 `main_source.fields`/`sources.*.fields`/顶层 derived fields 的场景
    - identity 丢失时的 content match 行为: 唯一匹配成功/歧义报错/找不到报错
  - CLI/编辑器体验: schema validate 不再因 object 条目直接失败,而是给出可行动的错误(若无法解析为 field_id).
