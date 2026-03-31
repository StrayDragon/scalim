## Context

YAML DSL 的校验链路同时服务:

- IDE/LSP(schema-only)
- CI/预提交(validate)
- runtime compile/run(最终语义边界)

目前存在若干“runtime 才会拒绝”的约束未被 schema/validate 表达,导致 fail-late 与诊断不一致(同一错误在不同入口出现不同失败点,甚至只在更晚阶段爆炸)。

## Goals / Non-Goals

**Goals:**

- 对齐 schema validate / validate / runtime compile 的可接受配置集合,将已存在的 runtime-only 约束前移到更早阶段 fail-fast。
- 错误提示更可行动: 能在 `scalim-cli yaml-dsl validate` 阶段定位到具体字段路径,避免用户必须跑到 compile/run 才发现。
- 生成物治理清晰:
  - schema SSOT 仅在 `src/scalim/dsl/by_yaml/schema_dsl/**`
  - schema json 通过 `just gen-yaml-dsl-schema` 生成,不手改生成物

**Non-Goals:**

- 不引入新的 DSL 语义/字段;仅把“已存在的语义边界”在 schema/validate 层面显式化。
- 不提供兼容/灰度: 对于当前 fail-late 写法,直接升级为 fail-fast(减少漂移面)。
- 不在本变更内处理“诊断 path 表达形式统一”(括号/点号)这一类系统性问题(另开 change 处理)。

## Decisions

1) **`source_id` / sources keys 的 identifier 规则收敛为单一正则**

- 使用 runtime 已存在的约束: `^[a-zA-Z_][a-zA-Z0-9_]*$`
- schema:
  - `main_source.source_id` 使用该 pattern
  - `sources` 的 mapping keys 通过 `propertyNames` 施加该 pattern
  - 为保持 `$import` 在编辑器(schema/LSP)下可用,`propertyNames` MUST 同时允许 key 为 `$import`
- validate:
  - 对 `sources` keys 与 `main_source.source_id` 进行同样的 pattern 校验,并给出稳定路径

2) **`loader`/`key` 的非空约束前移**

- schema 对 `main_source.loader`、`sources.*.loader` 增加 `minLength: 1`
- schema 对 `sources.*.key` 的 string/array item 使用 `field_id` pattern(拒绝空字符串)
- validate 在语义层同步拒绝空值,避免后续 resolver/IR 转换阶段才失败

3) **retry policy 完整性校验的边界(兼容 driver injection)**

- runtime compile 在合并 driver injection 后仍必须满足: `enabled=true` 时 effective `should_retry` 不得为空(已有约束)
- schema 本体无法感知 driver injection,因此本变更仅在 schema 中保证:
  - 当用户显式提供 `retry.should_retry` 时,必须为非空字符串
- CLI validate/schema validate 作为“YAML 独立物”校验入口,在无 driver injection 上下文时:
  - `enabled=true` 且缺失/为空 `should_retry` MUST 失败(避免 validate 放行但 compile 报错)
  - 统一文案: 提示“必须提供 should_retry(或由 driver injection 提供)”
  - 该完整性规则**仅落在 CLI 层**,不得下沉到共享 `ConfigValidator`/schema(否则会破坏 runtime compile 的 driver injection 用例)

4) **outputs 语义约束下沉到 schema**

- `outputs.*.container.streaming` 仅允许 `true`(可缺省;显式提供时必须为 true)
- detail outputs(未声明 `aggregate`)要求存在字段来源:
  - 显式声明非空 `fields`
  - 或通过 `from` 继承字段集合
  - schema 以条件约束表达该结构性约束(不试图在 schema 层理解继承的“实际 fields”)
- 为保持 `$import` 在编辑器(schema/LSP)下可用,该条件约束 MUST 显式允许仅声明 `$import` 的 `output_target` 通过 schema(不强制 `fields/from`)

## Risks / Trade-offs

- [严格性提升] schema validate/validate 将更早拒绝此前放行的写法: 缓解:
  - 明确这些写法在 runtime 中本就会失败
  - 为每个新增 fail-fast 提供可复制的修复建议与稳定路径
- [schema 表达力] 条件约束(if/then/anyOf)可能对部分编辑器提示体验有影响: 缓解:
  - 仅在 `outputs`/`retry` 等少数关键处使用,并保持结构简单
  - 通过回归测试锁定 schema validate 行为与错误路径

## Migration Plan

1) 修复 identifier:

- 将 `main_source.source_id` 与 `sources` 的 key 改为合法 identifier(字母/数字/下划线,且首字符非数字)

2) 修复空值:

- `loader: ""` 改为非空 loader 引用
- `key: ""` 改为合法 field_id,或复合键列表(每项非空)

3) 修复 retry:

- 当 `retry.enabled: true` 时补齐 `should_retry: "<callable ref>"`

4) 修复 outputs:

- `container.streaming` 不要显式写 `false`(若写出,必须为 `true`)
- detail output 必须显式 `fields` 或通过 `from` 继承 fields

## Open Questions

- (none)
