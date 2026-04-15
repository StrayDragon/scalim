# yaml-dsl-cli-validation (delta) Specification

## MODIFIED Requirements

### Requirement: CLI validate 与 schema validate 职责边界(避免重复诊断)
系统 SHALL 将 YAML DSL 校验命令明确分层,并保证 schema/unknown-fields 诊断一致且可预测:

- `PROJECT_CLI_NAME yaml-dsl validate` SHALL 使用内部语义校验器(internal validator)作为主校验入口,并输出可行动诊断(含定位信息)。
- `PROJECT_CLI_NAME yaml-dsl validate` MUST NOT 执行 JSONSchema 校验,也 MUST NOT 输出“已跳过 schema 校验 / jsonschema 不可用”类 warning(避免把工具链依赖带入 runtime 主线)。
- `PROJECT_CLI_NAME yaml-dsl schema validate` SHALL 作为 schema-only 校验入口,用于显式运行 JSON Schema 校验与 unknown-fields 诊断。
- `PROJECT_CLI_NAME yaml-dsl schema validate` MUST 依赖 `jsonschema` 且当缺失/不可用时 MUST fail-fast 并给出可行动提示（依赖应由 CLI 发行物自身声明）。
- `schema validate` MUST 使用一致的 schema errors 收集策略:
  - MUST 使用 `Draft7Validator.iter_errors`(或等价机制)产出**完整** schema 错误列表(不止第一条)
  - MUST 以稳定顺序输出 schema errors(例如按逻辑路径排序)
- 系统 MUST 避免对同一未知字段输出重复诊断:
  - 当 unknown-fields 与 schema additionalProperties 错误重叠时,MUST 去重
  - SHOULD 优先保留 unknown-fields 诊断(含 suggestions),并抑制 additionalProperties 造成的噪音 schema error

#### Scenario: validate 不依赖 jsonschema 且不输出 schema-skip warning
- **GIVEN** 运行环境未安装 `jsonschema`(或依赖不兼容/不可导入)
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate` 校验一个在内部语义校验层面有效的 YAML DSL 配置
- **THEN** 命令应正常执行并返回成功
- **AND** 输出中 MUST NOT 包含任何 “已跳过 schema 校验” 或 “jsonschema 不可用” 的 warning

#### Scenario: schema validate 收集多条 schema 错误(稳定排序)
- **GIVEN** 运行环境已安装 `jsonschema`
- **AND** 某 YAML DSL 配置在 schema 层面同时触发两条及以上相互独立的 schema 错误(路径不同)
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl schema validate <yaml>`
- **THEN** 输出 MUST 包含全部 schema 错误(不止第一条)
- **AND** 这些错误 MUST 以稳定顺序输出(例如按逻辑路径排序)

#### Scenario: unknown-fields 与 additionalProperties 不重复
- **GIVEN** 运行环境已安装 `jsonschema`
- **AND** 某 YAML DSL 配置包含未知字段 `main_source.unknown_field`
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl schema validate <yaml>`
- **THEN** 错误列表 MUST 包含 unknown-fields 的诊断(例如 "Unknown field 'unknown_field'" 且可包含 suggestions)
- **AND** 输出 MUST NOT 同时再包含同一路径上的 additionalProperties schema 错误诊断

#### Scenario: validate 可报告 init_var 节点形态错误
- **GIVEN** `outputs[0].container.path` 为 object 且包含额外键(例如 `{$init_var: output_path, other: 1}`)
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <yaml>`
- **THEN** 校验 MUST 失败
- **AND** 错误定位 MUST 指向 `outputs.0.container.path`

