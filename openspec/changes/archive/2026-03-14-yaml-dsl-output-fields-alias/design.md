## Context

当前 YAML DSL `outputs[*].fields` 仅接受 `field_id` 字符串列表. 旧配置中常见的写法是:

- 在 `main_source.fields` / `sources.*.fields` / 顶层 derived `fields` 中为字段定义对象设置 YAML anchor
- 在 `outputs[*].fields` 中使用 `*alias` 复用该字段对象

由于 `*alias` 在 PyYAML `safe_load` 后会展开为 dict,当前 schema/validator 会直接拒绝该条目,导致无法迁移.

系统内部已有“通过对象身份反查 field_id”的基础设施:
- `config_parsing.models.AliasIndex` 维护 `id(field_def.data) -> FieldDef` 映射
- `guardrails.loader.required_fields` 已支持条目为 YAML alias(dict) 并通过 alias_index 解析得到 `field_id`

本 change 将该能力扩展到 `outputs[*].fields`.

## Goals / Non-Goals

**Goals:**
- `outputs[*].fields` 同时支持:
  - `field_id` string 条目(保持现有写法)
  - YAML alias(dict) 条目(指向字段定义对象),可解析得到 `field_id`
- 匹配逻辑稳定且可诊断:
  - identity 匹配优先
  - identity 失败时允许“内容匹配”(仅唯一匹配时生效),并在歧义/无法匹配时给出明确错误与修复建议
- schema/hover 与运行时一致,避免 editor/CLI schema validate 阻断合法配置

**Non-Goals:**
- 不在 `outputs[*].fields` 中支持“覆写字段定义对象”的 merge/selector 语法(例如 `{<<: *quantity, name: ...}` 或 `{field_id: ..., name: ...}`)
- 不改变字段定义的声明位置规则与 computed/source 字段语义

## Decisions

### Decision: schema 允许 fields.items 为 string|object

在 `schema_dsl.models.outputs.OutputTargetConfig` 中,将 `fields` 的 items schema 从 `string` 放宽为 `anyOf: [string, object]`.
该 object 仅作为“alias 引用/匹配载体”,不作为新的字段声明语法.

原因:
- 与 `guardrails.loader.required_fields` 的 schema 形态保持一致,并允许 editor/CLI schema-only validation 不拦截该写法

### Decision: 解析阶段统一归一化为 field_id string

在 `config_parsing.parsers.outputs` 中将 `outputs[*].fields` 归一化为 `Tuple[str, ...]`:
- string: 直接 strip 得到 field_id
- dict:
  1) 优先通过 `field_def_index.alias_index.get(dict_obj)` 基于对象身份反查
  2) 若 identity 反查失败,在 `field_def_index.field_defs` 中做内容相等(`==`)匹配:
     - 唯一匹配: 使用该 FieldDef 的 `field_id`
     - 0 个匹配: 报错并提示改用 string field_id
     - >1 匹配: 报错并提示歧义(列出候选 field_id),要求改用 string field_id

原因:
- identity 反查覆盖最常见的 `&anchor` + `*alias` 场景
- 内容匹配为“PyYAML/中间处理导致对象身份丢失”的兜底,但在歧义时必须 fail-fast

### Decision: 错误信息优先可行动

当 dict 条目无法解析时,错误信息应包含:
- 逻辑路径: `outputs.<i>.fields.<j>`
- 原因: not an alias / not resolvable / ambiguous
- 建议: 改写为 `- "<field_id>"` 或避免对字段定义对象做 YAML merge

### Decision: validator/CLI 对不可解析条目提供更友好诊断

在 `config_parsing.validator.ConfigValidator.validate_report(...)` 中增加语义校验:

- 遍历 `outputs[*].fields`:
  - string 条目: 保持现有校验逻辑(仅做空串/类型等基础校验;字段存在性由后续编译链路保证)
  - object 条目: 必须能解析为唯一 `field_id`,否则作为 validation error 输出
- 对 object 条目的解析规则与运行时解析保持一致:
  1) 优先 identity(alias_index) 反查
  2) identity 失败时允许唯一 content match
- 对失败场景输出可行动诊断,至少包含:
  - `outputs.<i>.fields.<j>` 路径
  - 歧义时列出候选 `field_id` 列表
  - 提示改用字符串 `field_id`(或避免 YAML merge 导致 identity 丢失)

原因:
- `PROJECT_CLI_NAME yaml-dsl validate` 不走 jsonschema,应能在不依赖 schema-only 校验的情况下给出清晰提示
- 提升 IDE/CLI 体验,减少“运行到编译期才爆”的反复试错

## Risks / Trade-offs

- [风险] 内容匹配可能带来误判
  - → 缓解: 仅当唯一匹配时允许;歧义时 fail-fast 并提示改用 string
- [风险] schema 允许 object 可能掩盖用户错误(例如误把字段定义 dict 写进 fields)
  - → 缓解: 解析器必须严格验证 object 条目可解析为 field_id;否则报错(而不是 silently stringify dict)
- [风险] YAML merge(`<<`) 等操作会生成新 dict,可能丢失 alias 身份
  - → 缓解: 文档/hover 明确提示;内容匹配作为有限兜底

## Migration Plan

- 该变更为向后兼容:
  - 现有 `outputs[*].fields: ["order_id", ...]` 不变
  - 旧的 `- *alias` 写法恢复可用
- 发布后建议:
  - 对复杂/跨文件/merge 的场景,优先使用 string `field_id` 保持显式与可读性
