## Why

当前 YAML DSL 存在三条“校验语义入口”:

- schema-only 校验(`scalim-cli yaml-dsl schema validate`)
- 语义校验(`scalim-cli yaml-dsl validate`,内部 `ConfigValidator`)
- runtime compile/转换链路(解析/转换/编译)

但三者在若干关键约束上存在漂移,导致配置在 validate/schema validate 阶段通过,却在更晚的 compile/runtime 阶段失败(或只在某条入口报错),形成典型的 fail-late 问题,降低 CI/IDE 体验并增加排障成本。

## What Changes

- **BREAKING(validation)**: 收敛 schema/validate/runtime 的“可接受配置集合”:
  - schema 与 `validate` 将对若干当前 runtime-only 约束做 fail-fast,避免“validate 通过但 compile 失败”
  - 不做兼容: 对于“当前 validate/schema validate 放行但 runtime 会失败”的写法,统一改为更早拒绝
- 强化 demand JSON Schema 生成物的表达力,把已存在的语义约束下沉到 schema:
  - `main_source.source_id` 与 `sources` mapping keys 的 identifier pattern
  - `sources.*.loader` / `sources.*.key` / `main_source.loader` 的非空约束
  - `retry.should_retry` 的非空约束(当用户显式提供时必须为非空字符串; `enabled=true` 的“完整性”约束由 CLI validate 负责,并允许 runtime driver injection 场景)
  - `outputs.*.container.streaming` 仅允许 `true`
  - detail outputs 在未声明 `aggregate` 时要求存在有效字段来源(显式 `fields` 或通过 `from` 继承)
- 强化内部语义 validator(`ConfigValidator`)以与 schema/runtime 对齐(同一类错误在 validate 阶段即可定位)。
- 补充回归测试与 fixtures,锁定上述 fail-late 场景在 schema validate 与 validate 下的一致失败行为。

> 生成物边界: 不手改 `src/scalim/dsl/by_yaml/schema/*.gen.json`;修改 SSOT=`src/scalim/dsl/by_yaml/schema_dsl/**`,并通过 `just gen-yaml-dsl-schema` 刷新生成物。

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `demand-dsl`: 明确并在校验阶段 fail-fast: `source_id`/`sources` keys 必须为合法 identifier,且 `loader/key` 不允许空值。
- `yaml-dsl-schema`: demand JSON Schema 必须表达并拒绝上述 runtime-only 语义约束,减少 fail-late。
- `yaml-dsl-cli-validation`: `scalim-cli yaml-dsl validate` 与 `schema validate` 对上述形态必须给出一致且可定位的诊断。

## Impact

- YAML authoring/CI: 部分此前“validate/schema validate 通过但 runtime 会失败”的 YAML 将更早失败,需要按错误提示修正(例如修复 `source_id`,补齐 `should_retry`,避免 `streaming=false`).
- Schema SSOT: `src/scalim/dsl/by_yaml/schema_dsl/**` 与生成脚本 `scripts/gen-yaml-dsl-schema.py`.
- CLI/validator: `src/scalim/cli/yaml_dsl.py`, `src/scalim/dsl/by_yaml/config_parsing/validator.py` 与相关 validators.
- Tests: 需要补充/更新 CLI 输出回归与 schema-only 校验回归,确保错误路径稳定。

## Sequencing

- 建议在 `c30-yaml-dsl-diagnostics-path-normalization` 之后落地,以减少本 change 新增/更新的回归断言在 path 文本上的 churn(括号/点号口径统一后再收敛 fail-fast)。
