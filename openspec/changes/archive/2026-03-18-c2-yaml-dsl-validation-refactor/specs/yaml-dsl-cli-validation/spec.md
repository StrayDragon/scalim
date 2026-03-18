## MODIFIED Requirements

### Requirement: CLI validate 与 schema validate 职责边界(避免重复诊断)
系统 SHALL 将 YAML DSL 校验命令明确分层,并保证 schema/unknown-fields 诊断一致且可预测:

- `PROJECT_CLI_NAME yaml-dsl validate` SHALL 使用内部语义校验器(internal validator)作为主校验入口,并输出可行动诊断(含定位信息)。
- `PROJECT_CLI_NAME yaml-dsl validate` SHOULD 在 `jsonschema` 可用时执行 JSONSchema 校验以补充结构/类型诊断,但 MUST NOT **依赖** `jsonschema`:
  - 当运行环境未安装 `jsonschema`(或依赖不兼容/校验非预期失败)时,命令 MUST 输出 warning(可定位到 `(schema)`),并继续执行内部语义校验与 unknown-fields 检查。
  - warnings MUST NOT 使 validate 失败(退出码/`ok` 仅由 errors 决定)。
- 当 `jsonschema` 可用时,`validate` 与 `schema validate` MUST 使用一致的 schema errors 收集策略:
  - MUST 使用 `Draft7Validator.iter_errors`(或等价机制)产出**完整** schema 错误列表(不止第一条)
  - MUST 以稳定顺序输出 schema errors(例如按 `absolute_path` 排序)
- `PROJECT_CLI_NAME yaml-dsl schema validate` SHALL 作为 schema-only 校验入口,用于显式运行 JSON Schema 校验与 unknown-fields 诊断。
- 系统 MUST 避免对同一未知字段输出重复诊断:
  - 当 unknown-fields 与 schema additionalProperties 错误重叠时,MUST 去重
  - SHOULD 优先保留 unknown-fields 诊断(含 suggestions),并抑制 additionalProperties 造成的噪音 schema error

#### Scenario: validate 在无 jsonschema 环境仍可用且不失败
- **GIVEN** 运行环境未安装 `jsonschema`
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate` 校验一个在内部语义校验层面有效的 YAML DSL 配置
- **THEN** 命令应正常执行并返回成功
- **AND** 输出中 MUST 包含一条 warning 说明 JSONSchema 不可用且已跳过 schema 校验

#### Scenario: validate 收集多条 schema 错误(稳定排序)
- **GIVEN** 运行环境已安装 `jsonschema`
- **AND** 某 YAML DSL 配置在 schema 层面同时触发两条及以上相互独立的 schema 错误(路径不同)
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <yaml>`
- **THEN** 输出 MUST 包含全部 schema 错误(不止第一条)
- **AND** 这些错误 MUST 以稳定顺序输出(例如按逻辑路径排序)

#### Scenario: unknown-fields 与 additionalProperties 不重复
- **GIVEN** 运行环境已安装 `jsonschema`
- **AND** 某 YAML DSL 配置包含未知字段 `main_source.unknown_field`
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <yaml>`
- **THEN** 错误列表 MUST 包含 unknown-fields 的诊断(例如 "Unknown field 'unknown_field'" 且可包含 suggestions)
- **AND** 输出 MUST NOT 同时再包含同一路径上的 additionalProperties schema 错误诊断

#### Scenario: validate 可报告 init_var 节点形态错误(不依赖 jsonschema)
- **GIVEN** 运行环境未安装 `jsonschema`
- **AND** `outputs[0].container.path` 为 object 且包含额外键(例如 `{$init_var: output_path, other: 1}`)
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <yaml>`
- **THEN** 校验 MUST 失败
- **AND** 错误定位 MUST 指向 `outputs.0.container.path`

### Requirement: 严格未知字段校验
系统 SHALL 在 `PROJECT_CLI_NAME yaml-dsl validate` 默认模式下将未知字段视为校验错误,并在错误输出中包含未知字段路径(不再提供 `--strict`).
系统 MUST 确保该 unknown-fields 能力不依赖 `jsonschema` 可选依赖,并能够覆盖:

- schema 中 `oneOf/anyOf/allOf` 等组合分支产生的 mapping key 集合
- 数组 items 中的 mapping key（例如 `outputs[0]` 这类 list-of-object 节点）

#### Scenario: 严格模式未知字段
- **GIVEN** 运行环境未安装 `jsonschema`
- **WHEN** YAML 配置包含未知字段且用户运行 `PROJECT_CLI_NAME yaml-dsl validate`
- **THEN** 校验命令失败并报告未知字段路径

#### Scenario: list item 节点也做 unknown-fields 检测
- **GIVEN** 运行环境未安装 `jsonschema`
- **AND** YAML 配置在 `outputs[0].container` 内包含未知字段 `unknown_field`
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate`
- **THEN** 校验 MUST 失败
- **AND** 错误定位 MUST 指向 `outputs.0.container.unknown_field`
