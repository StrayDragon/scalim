## ADDED Requirements

### Requirement: CLI 提供显式开关以解析并执行 extensions analyzers
系统 SHALL 为 `PROJECT_CLI_NAME yaml-dsl validate` 提供显式开关以启用 `extensions` 的引用解析与 analyzer 执行,避免默认校验路径隐式执行用户代码.

#### Scenario: 默认 validate 不执行 extensions
- **GIVEN** YAML 包含 `extensions.analyze`
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <yaml>`
- **THEN** 命令 MUST 不解析/导入/执行 `extensions` 中的 Python 引用
- **AND** 命令 MUST 仍完成核心语义校验并输出结果

#### Scenario: 默认 validate 遇到扩展语法时给出可行动提示
- **GIVEN** YAML 使用扩展语法(例如 `outputs[*].container.type` 为非内置值,或 `outputs[*].aggregate.kind/ref` 为自定义值)
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <yaml>`(未开启 `--resolve-extensions`)
- **THEN** 命令 MUST 在输出中提示该配置依赖 extensions registry
- **AND** 命令 MUST 提示使用 `--resolve-extensions` 并提供 allowlist(或 `--trusted`)

#### Scenario: 开启开关后执行 analyzers
- **GIVEN** YAML 包含 `extensions.analyze`
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <yaml> --resolve-extensions`
- **THEN** 命令 MUST 解析并执行 analyzers 并将其 issues 合并到校验输出中

### Requirement: CLI 解析 extensions 时必须显式提供 allowlist
当 CLI 处于 `--resolve-extensions` 模式时,系统 MUST 要求用户显式提供 allowlist(例如 allowed_modules/allowed_functions),并在缺失时 fail-fast 给出可行动提示.

约束(建议的参数形态):
- `--allow-module <module_prefix>`: 可重复
- `--allow-function <module:attr_path>`: 可重复(与 `SecurePythonReferenceResolver.allowed_functions` 语义一致)
- `--trusted`: 作为快捷参数,等价于 allowlist 通配符(例如 `allowed_modules=["*"]`),并输出风险提示

#### Scenario: 未提供 allowlist 时 fail-fast
- **GIVEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <yaml> --resolve-extensions`
- **AND** 用户未提供任何 allowlist 参数
- **WHEN** CLI 尝试解析 extensions 引用
- **THEN** 命令 MUST 失败并提示需要提供 allowlist(或使用 trusted 快捷参数)

### Requirement: JSON 输出包含 extensions analyzer 的结构化 issues
系统 SHALL 在 `--json` 输出中包含扩展分析产生的结构化 issues,使 CI/脚本可区分来源.

#### Scenario: JSON 输出包含 extensions_issues
- **GIVEN** `extensions.analyze` 产生至少一个 warning
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <yaml> --resolve-extensions --json`
- **THEN** JSON 输出 MUST 包含扩展 issues 字段(例如 `extensions_warnings/extensions_errors` 或等价结构)

### Requirement: 提供 YAML DSL analyze 命令输出结构化分析报告
系统 SHALL 提供 `PROJECT_CLI_NAME yaml-dsl analyze` 命令,用于输出“编译期分析报告”(包含 extensions 摘要与 analyzers 结果),以支持 IDE/CI 的离线诊断与对拍.

#### Scenario: analyze 输出包含 extensions 摘要
- **GIVEN** YAML 启用 extensions 并注册了 compute functions/components/output formats
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl analyze <yaml> --resolve-extensions --json`
- **THEN** 输出 MUST 包含 extensions 摘要(例如 bundles 列表、注册表键集合、启用的 analyzers/transformers 列表)
