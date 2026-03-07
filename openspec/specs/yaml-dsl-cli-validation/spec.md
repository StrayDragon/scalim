# yaml-dsl-cli-validation Specification

**状态: ✅ 已实现**
## Purpose
定义 `PROJECT_CLI_NAME yaml-dsl ...` 的校验分层、严格模式、JSON 输出与诊断输出格式(含源码位置),以确保 CLI 校验结果可用于 IDE 跳转、CI 报告与脚本化消费,并避免与 schema 生成规范耦合.

## Related Code (as implemented)
- `src/IMPL_ROOT/cli/yaml_dsl.py` (cli validate/schema validate/show/path + linter-style output + location indexing)
- `src/IMPL_ROOT/dsl/by_yaml/config_parsing/validator.py` (`ConfigValidator` + strict unknown fields + `ConfigValidationError`)
- `src/IMPL_ROOT/dsl/by_yaml/config_parsing/unknown_fields.py` (unknown field detection + suggestions)
- `src/IMPL_ROOT/dsl/by_yaml/config_parsing/validators/issues.py` (`ValidationIssue` + `MAX_VALIDATION_ERROR_LINES`)
- `tests/test_yaml_dsl_cli_output.py` (CLI output regression tests)
- `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json` (schema input for schema-only validation and unknown-field checks)

## Implementation Notes (Current Behavior)
- `PROJECT_CLI_NAME yaml-dsl validate` 走内部语义 validator(`ConfigValidator.validate_report(...)`)并输出 linter 风格诊断(含 `path:line[:column]`).
- `PROJECT_CLI_NAME yaml-dsl schema validate` 走 JSON Schema(`jsonschema` 可选依赖)并补充 unknown fields/legacy fields 的诊断.
- CLI 的 `--json` 输出提供结构化 payload(含 `ok`/`errors`/`warnings`/`yaml_path`/`schema_path`)供脚本化消费.

## Requirements
### Requirement: CLI validate 与 schema validate 职责边界(避免重复诊断)
系统 SHALL 将 YAML DSL 校验命令明确分层:

- `PROJECT_CLI_NAME yaml-dsl validate` SHALL 仅使用内部语义校验器(internal validator)进行校验与诊断输出.
- `PROJECT_CLI_NAME yaml-dsl validate` MUST NOT 依赖 `jsonschema` 可选依赖(即使未安装 `jsonschema` 也不得输出“缺少依赖/跳过校验”的噪音日志).
- `PROJECT_CLI_NAME yaml-dsl schema validate` SHALL 作为 JSON Schema 校验入口,输出 schema 相关诊断(包含 schema 结构错误与 unknown fields).

#### Scenario: validate 不输出 schema 校验错误
- **WHEN** YAML 配置在 `output.fields` 中包含字符串条目(例如 `"order_id"`)
- **THEN** `PROJECT_CLI_NAME yaml-dsl validate` 输出应仅包含内部 validator 的可行动诊断
- **THEN** 输出中 MUST NOT 包含 `"Schema validation error"` 文案

#### Scenario: validate 不依赖 jsonschema
- **GIVEN** 运行环境未安装 `jsonschema`
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate` 校验 YAML DSL 配置
- **THEN** 命令应正常执行(以内部语义校验为准)且不得输出“jsonschema 不可用/跳过”等警告噪音

### Requirement: CLI Schema-Only Validation
系统 SHALL 提供 `PROJECT_CLI_NAME yaml-dsl schema validate` 命令,使用 JSON Schema 校验 YAML DSL 配置并支持 `--schema`、`--strict`、`--json` 参数.
该命令在严格模式下将未知字段视为错误并返回非零退出码.

#### Scenario: schema-only 校验命令
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl schema validate` 校验配置
- **THEN** 命令按 schema 校验并输出错误列表或 JSON 结果

### Requirement: CLI Schema Discovery
系统 SHALL 提供 `PROJECT_CLI_NAME yaml-dsl schema show` 输出当前 JSON Schema,并提供 `PROJECT_CLI_NAME yaml-dsl schema path` 输出 schema 的绝对路径.

#### Scenario: schema 查看
- **WHEN** 用户执行 `PROJECT_CLI_NAME yaml-dsl schema show`
- **THEN** 输出可解析的 JSON Schema

#### Scenario: schema 路径查看
- **WHEN** 用户执行 `PROJECT_CLI_NAME yaml-dsl schema path`
- **THEN** 输出 schema 的绝对路径

### Requirement: 严格未知字段校验
系统 SHALL 在 `PROJECT_CLI_NAME yaml-dsl validate --strict` 模式下将未知字段视为校验错误,并在错误输出中包含未知字段路径.

#### Scenario: 严格模式未知字段
- **WHEN** YAML 配置包含未知字段且使用 `PROJECT_CLI_NAME yaml-dsl validate --strict`
- **THEN** 校验命令失败并报告未知字段路径

### Requirement: 运行时 validator 错误列表包含 issue path
系统 MUST 在 `ConfigValidator.validate()` 抛出的 `ConfigValidationError.errors` 中包含可定位的逻辑路径信息:

- 当 `ValidationIssue.path` 非空时,对应的 `errors` 条目 MUST 以 `"{path}: "` 作为前缀并包含原始错误 message.
- 当 `ValidationIssue.path` 为空时,系统 MUST 仍输出原始错误 message(不强制添加前缀).

为防止错误过多时撑爆日志输出,系统 MUST 为 `ConfigValidationError.errors` 设置条目数量上限(实现可使用常量阈值),且 `ConfigValidationError.issues` MUST 保留完整 issue 列表供程序化读取.

#### Scenario: errors 条目包含 path 前缀
- **WHEN** YAML DSL 配置触发运行时校验错误,且至少一个错误具备非空 `ValidationIssue.path`
- **THEN** `ConfigValidationError.errors` 中 MUST 至少包含一条以 `"<path>: "` 开头的错误信息,用于定位到具体字段路径

#### Scenario: errors 被截断但 issues 完整
- **GIVEN** 某个配置可生成大量校验错误
- **WHEN** `ConfigValidator.validate()` 抛出 `ConfigValidationError`
- **THEN** `len(ConfigValidationError.errors)` MUST 小于等于实现上限且 `len(ConfigValidationError.issues)` MUST 大于等于 `len(ConfigValidationError.errors)`

### Requirement: 校验命令输出与 schema 一致性
系统 SHALL 在 `PROJECT_CLI_NAME yaml-dsl validate --json` 模式下输出结构化 JSON 结果,包含 `ok`、`errors` 与 `yaml_path`.
`PROJECT_CLI_NAME yaml-dsl schema validate` 替代旧的 schema 校验脚本,不再提供 schema compare 命令.

#### Scenario: JSON 输出
- **WHEN** 使用 `PROJECT_CLI_NAME yaml-dsl validate --json` 校验配置
- **THEN** 输出可解析的 JSON 且包含 `ok`、`errors` 与 `yaml_path`

### Requirement: CLI 校验输出包含源码位置
系统 SHALL 在 `PROJECT_CLI_NAME yaml-dsl validate` 与 `PROJECT_CLI_NAME yaml-dsl schema validate` 的非 JSON 输出中提供可跳转位置,格式至少包含 `path:line`(允许扩展到 `path:line:column`).
当无法解析具体位置时,系统 MUST 退化为文件级位置并保留路径 `(root)` 或逻辑路径文本.

#### Scenario: 派生字段依赖错误定位
- **WHEN** 派生字段依赖未知字段导致校验失败
- **THEN** 输出应包含对应 YAML 文件的 `path:line` 位置与错误信息

#### Scenario: schema-only 未知字段定位
- **WHEN** `yaml-dsl schema validate` 报告未知字段或 schema 错误
- **THEN** 输出应包含对应 YAML 文件的 `path:line` 位置

### Requirement: Linter/编译器风格输出
系统 SHALL 将非 JSON 输出统一为 linter/编译器风格,以单条诊断块展示 `ERROR/WARN`、消息与 `--> path:line[:column]`,并在 verbose 模式下附带源码片段.

#### Scenario: 使用 linter 风格输出
- **WHEN** 用户以默认非 JSON 方式运行校验
- **THEN** 每条诊断均按 `ERROR ... --> path:line` 形式输出并可直接跳转
