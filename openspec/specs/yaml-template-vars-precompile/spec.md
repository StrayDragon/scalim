# yaml-template-vars-precompile Specification

## Purpose
TBD - created by archiving change c5-yaml-template-vars-precompile. Update Purpose after archive.
## Requirements
### Requirement: template_vars enables LiteJinja2 precompile before YAML parse
系统 MUST 支持在读取 demand/workflow YAML 文本后、YAML parse 前执行 LiteJinja2 预编译,以便调用方通过 `template_vars` 注入 `{{ x }}`/`{% ... %}` 模板值.

当且仅当调用方显式提供 `template_vars`(非 `None`)时,系统 MUST 启用该预编译步骤;未提供时 MUST 不进行模板渲染(保持原有语义与安全边界).

#### Scenario: demand YAML supports unquoted placeholders
- **GIVEN** demand YAML 文本包含 `outputs.0.container.path: {{ output_path }}` 形式的未加引号占位符
- **WHEN** 调用方执行 `compile(..., template_vars={"output_path": "./output/report.xlsx"})`
- **THEN** 系统 MUST 先完成模板渲染再进行 YAML parse
- **AND** YAML parse MUST 成功
- **AND** 编译后的输出路径 MUST 等于 `"./output/report.xlsx"`

#### Scenario: workflow YAML fields can be templated
- **GIVEN** workflow YAML 文本包含 `workflow.options.max_concurrency: {{ max_concurrency }}`
- **WHEN** 调用方执行 `run_workflow(..., template_vars={"max_concurrency": 3})`
- **THEN** workflow 配置加载 MUST 先完成模板渲染再进行 YAML parse
- **AND** 编译后的 `max_concurrency` MUST 等于 `3`

### Requirement: template precompile applies to demand import fragments
当 demand YAML 启用 `template_vars` 预编译且配置中包含 `imports/$import` 时,系统 MUST 对被 imports 机制加载的 fragment YAML 文件执行同一份 `template_vars` 的文本预编译(发生在 fragment 的 YAML parse 前).

#### Scenario: imported fragments can reference template_vars
- **GIVEN** demand YAML 通过 `imports/$import` 引入某 fragment mapping
- **AND** fragment YAML 文本中包含 `{{ x }}` 占位符
- **WHEN** 调用方执行 `compile(..., template_vars={"x": "v"})`
- **THEN** imports expansion MUST 成功
- **AND** 合并后的 demand 配置 MUST 反映 `"v"` 的注入结果

### Requirement: missing template vars fail fast (strict-undefined)
当启用 `template_vars` 预编译时,系统 MUST 以 strict-undefined 语义渲染模板:

- 若模板表达式引用了未提供变量且未显式兜底,渲染 MUST fail-fast
- 错误消息 MUST 包含缺失变量名
- 若缺失发生在 import fragment 中,错误 MUST 包含 import trace(至少包含 fragment 文件路径)

#### Scenario: missing variable fails fast with a clear message
- **GIVEN** demand/workflow YAML 模板中包含 `{{ missing }}` 引用
- **WHEN** 调用方执行入口且 `template_vars` 不包含 key `missing`
- **THEN** 系统 MUST fail-fast
- **AND** 错误 MUST 包含缺失变量名 `missing`

### Requirement: default filter can provide an explicit fallback under strict-undefined
当启用 strict-undefined 时,若模板对缺失变量显式使用 `| default(<value>)` 兜底,系统 MUST 将该表达式渲染为兜底值,并允许整体模板渲染成功.

#### Scenario: default filter replaces missing variables
- **GIVEN** YAML 模板中包含 `{{ missing | default('x') }}`
- **WHEN** 调用方执行入口且 `template_vars` 不包含 key `missing`
- **THEN** 模板渲染 MUST 成功
- **AND** 渲染结果 MUST 使用 `"x"` 作为该表达式输出

### Requirement: template precompile MUST enforce a rendered-YAML size limit

当启用 `template_vars` 预编译时,系统 MUST 对渲染后的 YAML 文本施加“渲染后大小上限”,以避免模板放大导致内存/CPU 放大或后续 YAML parse 退化.

约束:
- 上限 MUST 覆盖 demand/workflow YAML 本体以及 imports 机制加载的 fragment 文本。
- 上限 MUST 在 YAML parse 前检查（对渲染后的文本生效）。
- 超限时系统 MUST fail-fast。
- 错误信息 MUST 包含: 所在输入类型(demand/workflow/fragment)、相关文件路径(若有)、`rendered_len` 与 `max_len`。
- 错误信息 MUST NOT 泄露渲染后的 YAML 文本内容（不得回显正文片段）。

#### Scenario: oversized rendered demand YAML fails fast
- **GIVEN** demand YAML 启用 `template_vars` 预编译
- **AND** 渲染后的 YAML 文本长度超过 `max_len`
- **WHEN** 调用方执行 `compile/run`
- **THEN** 系统 MUST 在 YAML parse 前 fail-fast
- **AND** 错误信息 MUST 包含 `rendered_len` 与 `max_len`

#### Scenario: oversized rendered import fragment fails fast with import trace
- **GIVEN** demand YAML 启用 imports 且 fragment 也启用同一份 `template_vars` 预编译
- **AND** 某 fragment 渲染后长度超过 `max_len`
- **WHEN** 调用方执行 `compile/run`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 包含 fragment 路径(或等价 import trace)
