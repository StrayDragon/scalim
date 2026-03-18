# yaml-dsl-cli-validation Specification

**状态: ✅ 已实现**
## Purpose
定义 `PROJECT_CLI_NAME yaml-dsl ...` 的校验分层、严格模式、JSON 输出与诊断输出格式(含源码位置),以确保 CLI 校验结果可用于 IDE 跳转、CI 报告与脚本化消费,并避免与 schema 生成规范耦合.

## Related Code (as implemented)
- `src/IMPL_ROOT/cli/yaml_dsl.py` (cli validate/schema validate/show/path + linter-style output + location indexing)
- `src/IMPL_ROOT/cli/yaml_dsl_lsp.py` (upsert-lsp-comment)
- `src/IMPL_ROOT/dsl/by_yaml/config_parsing/validator.py` (`ConfigValidator` + strict unknown fields + `ConfigValidationError`)
- `src/IMPL_ROOT/dsl/by_yaml/config_parsing/unknown_fields.py` (unknown field detection + suggestions)
- `src/IMPL_ROOT/dsl/by_yaml/config_parsing/validators/issues.py` (`ValidationIssue` + `MAX_VALIDATION_ERROR_LINES`)
- `tests/test_yaml_dsl_cli_output.py` (CLI output regression tests)
- `tests/test_yaml_dsl_lsp_comment.py` (upsert-lsp-comment regression tests)
- `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json` (schema input for schema-only validation and unknown-field checks)

## Implementation Notes (Current Behavior)
- `PROJECT_CLI_NAME yaml-dsl validate` 走内部语义 validator(`ConfigValidator.validate_report(...)`)并输出 linter 风格诊断(含 `path:line[:column]`);当 `jsonschema` 可用时会执行 JSONSchema 校验补充结构/类型诊断,不可用/异常时以 warning 形式提示并继续.
- `PROJECT_CLI_NAME yaml-dsl schema validate` 走 JSON Schema(依赖 `jsonschema`)并补充 unknown fields/legacy fields 的诊断.
- CLI 的 `--json` 输出提供结构化 payload(含 `ok`/`errors`/`warnings`/`yaml_path`/`schema_path`)供脚本化消费.
## Requirements
### Requirement: CLI validate 与 schema validate 职责边界(避免重复诊断)
系统 SHALL 将 YAML DSL 校验命令明确分层,并保证 schema/unknown-fields 诊断一致且可预测:

- `PROJECT_CLI_NAME yaml-dsl validate` SHALL 使用内部语义校验器(internal validator)作为主校验入口,并输出可行动诊断(含定位信息)。
- `PROJECT_CLI_NAME yaml-dsl validate` SHOULD 在 `jsonschema` 可用时执行 JSONSchema 校验以补充结构/类型诊断,但 MUST NOT **依赖** `jsonschema`:
  - 当运行环境未安装 `jsonschema`(或依赖不兼容/校验非预期失败)时,命令 MUST 输出 warning(可定位到 `(schema)`),并继续执行内部语义校验与 unknown-fields 检查。
  - warnings MUST NOT 使 validate 失败(退出码/`ok` 仅由 errors 决定)。
- `PROJECT_CLI_NAME yaml-dsl schema validate` SHALL 作为 schema-only 校验入口,用于显式运行 JSON Schema 校验与 unknown-fields 诊断。
- 当 `jsonschema` 可用时,`validate` 与 `schema validate` MUST 使用一致的 schema errors 收集策略:
  - MUST 使用 `Draft7Validator.iter_errors`(或等价机制)产出**完整** schema 错误列表(不止第一条)
  - MUST 以稳定顺序输出 schema errors(例如按逻辑路径排序)
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

### Requirement: JSONSchema 错误收集(完整 + 稳定 + 去噪)
当 `jsonschema` 可用时,系统 MUST 使用 `Draft7Validator.iter_errors(...)` 收集 JSONSchema 校验的**完整错误列表**(不只报第一条),并保证输出顺序稳定:

- 错误列表 MUST 按 `error.absolute_path` + `error.message` 的组合稳定排序(避免因遍历顺序波动导致回归困难).
- 对 `oneOf/anyOf` 的 `error.context` 子错误:
  - 默认输出 SHOULD 保持简洁,不展开 context 细节噪音
  - `--verbose` 模式 SHOULD 展开输出 context 子错误以辅助调试
- 当命令同时启用 unknown-fields(严格未知字段)检查时,系统 SHOULD 避免重复诊断:
  - `additionalProperties` 类型的 schema errors SHOULD 被过滤(或与 unknown-fields 做去重)
  - unknown-fields 的“Unknown field + suggestions”诊断 MUST 优先保留

#### Scenario: schema-only 输出完整且稳定排序的 schema errors
- **GIVEN** 某 YAML 配置在多个位置违反 JSON Schema
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl schema validate <yaml>`
- **THEN** 输出 MUST 包含全部 schema errors(而不是只报第一条)
- **AND** 输出顺序 MUST 稳定(相同输入在多次运行中顺序一致)

#### Scenario: verbose 才展开 oneOf/anyOf context 子错误
- **GIVEN** 某 YAML 配置触发 `oneOf/anyOf` 失败且存在 `error.context` 子错误
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl schema validate <yaml>`(非 verbose)
- **THEN** 输出 SHOULD 不包含 `context` 子错误明细(仅给出主错误)
- **AND** 当用户运行 `PROJECT_CLI_NAME yaml-dsl schema validate --verbose <yaml>` 时输出 SHOULD 包含 `context` 子错误明细

### Requirement: CLI Schema Discovery
系统 SHALL 提供 `PROJECT_CLI_NAME yaml-dsl schema show` 输出当前 JSON Schema,并提供 `PROJECT_CLI_NAME yaml-dsl schema path` 输出 schema 的绝对路径.

#### Scenario: schema 查看
- **WHEN** 用户执行 `PROJECT_CLI_NAME yaml-dsl schema show`
- **THEN** 输出可解析的 JSON Schema

#### Scenario: schema 路径查看
- **WHEN** 用户执行 `PROJECT_CLI_NAME yaml-dsl schema path`
- **THEN** 输出 schema 的绝对路径

### Requirement: 严格未知字段校验
系统 SHALL 在 `PROJECT_CLI_NAME yaml-dsl validate` 默认模式下将未知字段视为校验错误,并在错误输出中包含未知字段路径(不再提供 `--strict`).
系统 MUST 确保该 unknown-fields 能力不依赖 `jsonschema` 可选依赖,并能够覆盖:

- schema 中 `oneOf/anyOf/allOf` 等组合分支产生的 mapping key 集合
- 数组 items 中的 mapping key（例如 `outputs[0]` 这类 list-of-object 节点）

#### Scenario: 严格模式未知字段
- **WHEN** YAML 配置包含未知字段且用户运行 `PROJECT_CLI_NAME yaml-dsl validate`
- **THEN** 校验命令失败并报告未知字段路径

#### Scenario: list item 节点也做 unknown-fields 检测
- **GIVEN** 运行环境未安装 `jsonschema`
- **AND** YAML 配置在 `outputs[0].container` 内包含未知字段 `unknown_field`
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate`
- **THEN** 校验 MUST 失败
- **AND** 错误定位 MUST 指向 `outputs.0.container.unknown_field`

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

### Requirement: validate 对 `outputs.*.fields` object 条目给出可行动诊断
系统 MUST 在 `PROJECT_CLI_NAME yaml-dsl validate` 的内部语义校验中,对 `outputs[*].fields` 的 object 条目执行解析校验:

- 若 object 条目无法解析为唯一 `field_id`,校验 MUST 失败
- 错误 MUST 包含可行动提示(例如候选 `field_id` 列表/歧义原因/建议改用 string `field_id`)
- 错误 MUST 以 `outputs.<i>.fields.<j>` 作为定位路径,以便 CLI 能附加正确的 `path:line[:column]`

#### Scenario: object 条目无法解析时报错并提示改用 field_id
- **GIVEN** `outputs[0].fields[0]` 为 object 条目且无法匹配到任何字段定义
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <yaml>`
- **THEN** 校验 MUST 失败
- **AND** 错误消息 MUST 提示该条目无法解析为 `field_id` 并建议改用 string `field_id`

#### Scenario: object 条目歧义时报错并列出候选字段
- **GIVEN** `outputs[0].fields[0]` 为 object 条目且可匹配到多个字段定义
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <yaml>`
- **THEN** 校验 MUST 失败
- **AND** 错误消息 MUST 包含候选字段的 `field_id` 列表并建议改用 string `field_id`

### Requirement: CLI can upsert schema modeline in YAML files (IntelliJ compatible)
系统 SHALL 提供 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment` 命令,用于对用户给定的一组 YAML 文件插入或更新 schema modeline.

系统 MUST 识别以下两种 schema modeline:
- `# yaml-language-server: $schema=<...>`(Red Hat YAML Language Server)
- `# $schema: <...>`(IntelliJ)

系统 MUST 支持通过 `--comment-style {all,jetbrains,redhat}` 控制写入风格:
- `all`(默认): 同时 upsert 两种 modeline
- `jetbrains`: 仅 upsert `# $schema: <schema-ref>`
- `redhat`: 仅 upsert `# yaml-language-server: $schema=<schema-ref>`

该命令 MUST:
- 接受一个或多个 YAML 文件路径作为位置参数
- 在文件头部注释块内 upsert schema header:
  - 若在前 N 行(建议 N=10)内,在遇到第一行非注释内容前发现任意一种 schema modeline,则按 `--comment-style` 期望结果进行更新/移除/去重
  - 否则将期望的 schema modeline(一个或两个)插入为文件第一行开始的注释块,并在最后一个 schema modeline 后保留一个空行
- 当目标文件已经包含期望的 schema modeline(集合与内容均一致)时,不得改写文件内容(幂等)

#### Scenario: comment-style=all 时插入两种 header
- **GIVEN** 某 YAML 文件头部不包含 schema modeline
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --comment-style all --type demand <file.yaml>`
- **THEN** 该文件头两行依次为:
  - `# yaml-language-server: $schema=.../demand.gen.json`
  - `# $schema: .../demand.gen.json`

#### Scenario: comment-style=jetbrains 时只保留 IntelliJ header
- **GIVEN** 某 YAML 文件头部包含两种 schema modeline
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --comment-style jetbrains --type demand <file.yaml>`
- **THEN** 文件头部仅保留 `# $schema: .../demand.gen.json`
- **AND** 不再包含 `yaml-language-server` modeline

#### Scenario: comment-style=redhat 时只保留 yaml-language-server header
- **GIVEN** 某 YAML 文件头部包含两种 schema modeline
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --comment-style redhat --type demand <file.yaml>`
- **THEN** 文件头部仅保留 `# yaml-language-server: $schema=.../demand.gen.json`
- **AND** 不再包含 `# $schema:` modeline

### Requirement: upsert-lsp-comment resolves schema reference from type + schema-path
系统 MUST 在 `upsert-lsp-comment` 中提供 `--type` 与 `--schema-path` 组合的 schema 引用解析,用于生成最终写入的 `<schema-ref>`.

解析规则:
- `--type` 默认值为 `demand`
- `--schema-path` 默认值为内置 schema 目录的本地绝对路径(即 `src/IMPL_ROOT/dsl/by_yaml/schema/` 在包内的实际路径)
- `--schema-path` 允许是 base URL/base 目录,也允许是完整 schema URL/文件路径
- 若 `--schema-path` 以 `.json` 结尾,系统 MUST 将其视为完整 schema 引用并直接使用
- 否则系统 MUST 将其视为 base,并拼接 `/<type>.gen.json` 生成最终引用

#### Scenario: schema-path 为 base URL 时拼接文件名
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --type workflow --schema-path http://127.0.0.1:62831 <file.yaml>`
- **THEN** 写入的 schema ref 以 `/workflow.gen.json` 结尾

#### Scenario: schema-path 为完整 URL 时直接使用
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --schema-path http://example.invalid/custom.json <file.yaml>`
- **THEN** 写入的 schema ref 为 `http://example.invalid/custom.json`

#### Scenario: schema-path 缺省时使用内置 schema 目录默认值
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --type demand <file.yaml>`
- **THEN** 写入的 schema ref 以 `/demand.gen.json` 结尾
