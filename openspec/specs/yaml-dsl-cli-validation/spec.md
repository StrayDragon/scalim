# yaml-dsl-cli-validation Specification

**状态: ✅ 已实现**
## Purpose
定义 `PROJECT_CLI_NAME yaml-dsl ...` 的校验分层、严格模式、JSON 输出与诊断输出格式(含源码位置),以确保 CLI 校验结果可用于 IDE 跳转、CI 报告与脚本化消费,并避免与 schema 生成规范耦合.

## Related Code (as implemented)
- `packages/scalim-cli/src/scalim_cli/yaml_dsl.py` (cli validate/schema validate/show/path + linter-style output + location indexing)
- `packages/scalim-cli/src/scalim_cli/yaml_dsl_lsp.py` (upsert-lsp-comment)
- `src/IMPL_ROOT/dsl/yaml_dsl/_internal/config_parsing/validator.py` (`ConfigValidator` + strict unknown fields + `ConfigValidationError`)
- `src/IMPL_ROOT/dsl/yaml_dsl/_internal/config_parsing/unknown_fields.py` (unknown field detection + suggestions)
- `src/IMPL_ROOT/dsl/yaml_dsl/_internal/config_parsing/validators/issues.py` (`ValidationIssue` + `MAX_VALIDATION_ERROR_LINES`)
- `tests/yaml_dsl/test_yaml_dsl_cli_output.py` (CLI output regression tests)
- `tests/yaml_dsl/test_yaml_dsl_lsp_comment.py` (upsert-lsp-comment regression tests)
- `src/IMPL_ROOT/dsl/yaml_dsl/schema/demand.gen.json` (schema input for schema-only validation and unknown-field checks)

## Implementation Notes (Current Behavior)
- `PROJECT_CLI_NAME yaml-dsl validate` 走内部语义 validator(`ConfigValidator.validate_report(...)`)并输出 linter 风格诊断(含 `path:line[:column]`);不执行 JSONSchema 校验,也不输出“已跳过 schema 校验 / jsonschema 不可用”类 warning.
- `PROJECT_CLI_NAME yaml-dsl schema validate` 走 JSON Schema(依赖 `jsonschema`)并补充 unknown fields/legacy fields 的诊断;当 `jsonschema` 缺失/不可用时 fail-fast.
- CLI 的 `--json` 输出提供结构化 payload(含 `ok`/`errors`/`warnings`/`yaml_path`/`schema_path`)供脚本化消费.
## Requirements
### Requirement: CLI implementation MAY live outside runtime core but MUST preserve validation contracts

系统 MUST 允许将 `PROJECT_CLI_NAME yaml-dsl ...` 的 CLI 实现迁移到独立发行物（例如 `scalim-cli`）以降低 runtime core 的维护负担，但该迁移 MUST 满足：

- CLI 的对外行为契约（退出码、`--json` payload 结构、linter-style 输出格式、workflow validate 合并结构等）MUST 保持与现有规范一致；
- CLI 的校验语义 MUST 委托 `scalim` 内的可复用 service 层（例如 `dsl/yaml_dsl/validation_service.py`），不得在 CLI 包中复制一份语义真相；
- runtime core（`src/IMPL_ROOT/`）MUST 仍可在不安装 CLI 发行物的环境中被 import 并用于 compile/validate/run/workflow。

#### Scenario: runtime imports succeed without CLI distribution
- **GIVEN** 环境未安装 CLI 发行物（例如 `scalim-cli`）
- **WHEN** 调用方导入并使用 runtime 入口（例如 `scalim.dsl.yaml_dsl.run`）
- **THEN** 导入与运行 MUST 成功

### Requirement: CLI validation MUST reuse the unified YAML load facade

系统 MUST 要求 `PROJECT_CLI_NAME yaml-dsl validate`（或等价 CLI 校验入口）复用统一的 YAML load facade,以保证与 runtime/compile/workflow validate 的一致性.

#### Scenario: CLI validate matches compile error structure
- **WHEN** 某份 YAML 在 runtime compile/run 中因 parse/duplicate key 失败
- **THEN** 同一份 YAML 在 CLI validate 下 MUST 以相同 ErrorEnvelope 结构失败（差异仅限入口标识/命令上下文）

### Requirement: YAML validation contracts MUST be centralized as SSOT across entrypoints

对于 YAML DSL 的稳定输入契约规则（例如 Excel `sheet_name` 校验、`outputs[*].name` 命名规则），系统 MUST 将其集中为单一 SSOT 实现，并在所有入口复用，以避免语义漂移：

- workflow compile、runtime compile、internal parsers 与 CLI validate MUST 复用同一套校验规则实现
- 对同一非法输入，不同入口 MUST 给出一致的接受/拒绝结果
- 错误信息 MUST 使用单一模板并包含一致的关键字段（至少包含逻辑 path、失败原因与可行动修复建议），以便 CLI/LSP 稳定定位与文档治理

#### Scenario: invalid sheet_name fails consistently across workflow and runtime compile
- **GIVEN** 用户提供一个非法的 Excel sheet_name（例如空值/超长/包含非法字符）
- **WHEN** 分别通过 workflow compile 与 runtime compile 入口进行校验
- **THEN** 两个入口 MUST 均 fail-fast
- **AND** 诊断信息 MUST 指向同一逻辑 path 并表达一致的失败原因

#### Scenario: invalid output name fails consistently across parsers
- **GIVEN** 用户提供一个不满足命名规则的 `outputs[*].name`
- **WHEN** 通过 internal parser 与 CLI validate 入口进行校验
- **THEN** 两个入口 MUST 给出一致的失败结论与关键诊断字段

### Requirement: CLI validate MUST delegate validation logic to a reusable service layer

系统 MUST 将 `PROJECT_CLI_NAME yaml-dsl validate` 的校验逻辑下沉为可复用的服务层,使 CLI 层仅负责参数解析与输出渲染:

- 校验服务层 MUST 接收结构化输入（yaml_path/schema_path/yaml_type/path_aliases/allowed_yaml_roots 等）并返回结构化 `ValidationPayload`（errors/warnings/locations/附加信息）
- CLI 层 MUST 仅做:
  - args → service 调用
  - payload → json/text renderer
  - exit code 决策
- Phase 0（迁移期）服务层化重构 MUST 保持对外输出结构与关键字段一致（或在变更中显式声明差异）

#### Scenario: service returns a payload that CLI can render without extra validation logic
- **GIVEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <file>`
- **WHEN** CLI 调用校验服务层
- **THEN** service MUST 返回包含 errors/warnings/locations 的结构化 payload
- **AND** CLI 渲染输出时 MUST 不需要重新实现业务校验分支

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

### Requirement: validate and schema validate MUST catch known fail-late cases consistently
系统 MUST 确保 `scalim-cli yaml-dsl validate` 与 `scalim-cli yaml-dsl schema validate` 对下列形态给出一致的失败结果(非零退出码),且错误信息可定位到对应路径:

- `sources` 出现非法 mapping key(空 key 或不匹配 identifier pattern)
- `main_source.loader` / `sources.*.loader` 为空字符串
- `sources.*.key` 为空字符串(或列表包含空字符串)
- `retry.enabled=true` 且缺失/为空 `should_retry`(在 CLI 校验上下文中;提示可由 driver injection 提供)
- `outputs.*.container.streaming=false`
- detail output(未声明 aggregate)缺失 `fields` 且缺失 `from`

#### Scenario: validate fails early instead of compile-time failure
- **GIVEN** 某 demand YAML 含上述任一错误形态
- **WHEN** 用户执行 `scalim-cli yaml-dsl validate <file.yaml>`
- **THEN** 命令 MUST 失败
- **AND** 错误 MUST 指向对应逻辑路径(例如 `sources.orders.key`, `outputs.0.container.streaming`)

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

### Requirement: `ValidationIssue.path` MUST 使用单一 canonical 口径以稳定映射到源码位置
系统 MUST 对 `ValidationIssue.path` 采用单一 canonical 口径,并确保该口径可以稳定映射到 YAML 源码位置:

- canonical 口径 MUST 使用点号分段
- 数组索引 MUST 使用数字段(`outputs.0.fields.1`)
- CLI/定位层 MUST 对旧 `[]` 索引形态做 normalization,至少支持将 `foo[0].bar[1]` 归一化为 `foo.0.bar.1`

#### Scenario: bracket path still yields precise location
- **GIVEN** 某 validator 仍产出 issue path `outputs[0].container.path`
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <file.yaml>`
- **THEN** CLI 输出 MUST 能定位到 `outputs.0.container.path` 对应的 `path:line[:column]`

#### Scenario: CLI outputs canonical dot path
- **WHEN** CLI 输出某条诊断
- **THEN** 该诊断展示的逻辑路径 MUST 为 canonical 点号口径(不出现 bracket)

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
- `--schema-path` 默认值为内置 schema 目录的本地绝对路径(即 `src/IMPL_ROOT/dsl/yaml_dsl/schema/` 在包内的实际路径)
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
