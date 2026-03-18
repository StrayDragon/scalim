## MODIFIED Requirements

### Requirement: CLI validate 与 schema validate 职责边界(避免重复诊断)
系统 SHALL 将 YAML DSL 校验命令明确分层:

- `PROJECT_CLI_NAME yaml-dsl validate` SHALL 使用内部语义校验器(internal validator)作为主校验入口,并输出可行动诊断(含定位信息)。
- `PROJECT_CLI_NAME yaml-dsl validate` SHOULD 在 `jsonschema` 可用时执行 JSONSchema 校验以补充结构/类型诊断,但 MUST NOT **依赖** `jsonschema`:
  - 当运行环境未安装 `jsonschema`(或依赖不兼容/校验非预期失败)时,命令 MUST 输出 warning(可定位到 `(schema)`),并继续执行内部语义校验与 unknown-fields 检查。
  - warnings MUST NOT 使 validate 失败(退出码/`ok` 仅由 errors 决定)。
- `PROJECT_CLI_NAME yaml-dsl schema validate` SHALL 作为 schema-only 校验入口,用于显式运行 JSON Schema 校验与 unknown-fields 诊断。

#### Scenario: validate 在无 jsonschema 环境仍可用且不失败
- **GIVEN** 运行环境未安装 `jsonschema`
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate` 校验一个在内部语义校验层面有效的 YAML DSL 配置
- **THEN** 命令应正常执行并返回成功
- **AND** 输出中 MUST 包含一条 warning 说明 JSONSchema 不可用且已跳过 schema 校验

#### Scenario: validate 可报告 init_var 节点形态错误
- **GIVEN** `outputs[0].container.path` 为 object 且包含额外键(例如 `{$init_var: output_path, other: 1}`)
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <yaml>`
- **THEN** 校验 MUST 失败
- **AND** 错误定位 MUST 指向 `outputs.0.container.path`

### Requirement: CLI Schema-Only Validation
系统 SHALL 提供 `PROJECT_CLI_NAME yaml-dsl schema validate` 命令,使用 JSON Schema 校验 YAML DSL 配置并支持 `--schema`、`--json` 参数.
该命令默认将未知字段视为错误并返回非零退出码(不再需要 `--strict`).

#### Scenario: schema-only 校验命令
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl schema validate` 校验配置
- **THEN** 命令按 schema 校验并输出错误列表或 JSON 结果

### Requirement: 严格未知字段校验
系统 SHALL 在 `PROJECT_CLI_NAME yaml-dsl validate` 默认模式下将未知字段视为校验错误,并在错误输出中包含未知字段路径(不再提供 `--strict`).

#### Scenario: 默认严格模式未知字段
- **WHEN** YAML 配置包含未知字段且用户运行 `PROJECT_CLI_NAME yaml-dsl validate`
- **THEN** 校验命令失败并报告未知字段路径

