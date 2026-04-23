## MODIFIED Requirements

### Requirement: demand and workflow YAML MUST support `resources.files` as the unified file-output resource surface

系统 MUST 提供 `resources.files` 作为非 book 文件输出的统一资源入口,并在 demand/workflow 两类 YAML 中保持一致:

- demand: `resources.files.<file_id>`
- workflow: `workflow.resources.files.<file_id>`

约束:

- `<file_id>` MUST 为非空字符串且在同一 mapping 内唯一
- `resources.files.<file_id>` MUST 为 mapping
- v1 仅允许 `csv_file: <mapping>` 分支写法
- `resources.files.<file_id>.csv_file.path` MUST 为非空字符串或 `{$init_var: <name>}`
- `resources.files.<file_id>.csv_file.encoding` MAY 存在且 MUST 为非空字符串(默认 `utf-8`)
- `resources.files.<file_id>.csv_file.path` 语义 MUST 为 **输出 root 目录**（版本化输出 D-2），而不是最终文件路径
- 相对路径 MUST 以声明该资源的 YAML 文件所在目录为基准解析
- 系统 MUST 基于 `file_id` 与 `version_id` 推导最终输出路径：
  - final path MUST 等价于 `<root>/versions/<version_id>/files/<file_id>.csv`
- legacy `write_lock` 配置面 MUST 被移除；若用户仍提供该字段，系统 MUST fail-fast 并给出迁移提示

其中 `version_id` 取值约束：

- standalone demand: `version_id` MUST 等于该 demand 的 `run_id`
- workflow: `version_id` MUST 等于该 workflow 的 `workflow_exec_id`

legacy `kind` discriminator MUST 被移除；若用户仍声明 `resources.files.<file_id>.kind`，系统 MUST fail-fast 并给出迁移提示（迁移到 `resources.files.<file_id>.csv_file: {...}` 分支写法）。

（demand-only）imports 支持：

- demand YAML MAY 在 `resources.files.<file_id>` 节点级声明 `$import`（导入整个资源节点 mapping）
- demand YAML MAY 在 `resources.files.<file_id>.csv_file` 分支级声明 `$import`
- 当 `$import` 与本地键并存时，imports expansion MUST 以“导入值为 defaults、本地覆盖导入值”的语义合并
- workflow YAML MUST NOT 支持 `imports`/`$import`（schema 与 runtime 均 fail-fast）

#### Scenario: file resource passes schema validation
- **WHEN** demand YAML 声明 `resources.files.detail.csv_file.path=./out`
- **THEN** schema-only 校验 MUST 通过

#### Scenario: demand node-level $import passes schema-only validation
- **WHEN** demand YAML 声明 `resources.files.detail.$import=common.resources.files.detail`
- **THEN** schema-only 校验 MUST 通过

#### Scenario: demand branch-level $import passes schema-only validation
- **WHEN** demand YAML 声明 `resources.files.detail.csv_file.$import=common.resources.files.detail_csv_file`
- **THEN** schema-only 校验 MUST 通过

#### Scenario: legacy kind discriminator is rejected with migration hint
- **WHEN** 用户仍声明 `resources.files.detail.kind=csv_file`
- **THEN** schema-only 与 runtime 校验 MUST fail-fast
- **AND** 错误信息 MUST 提示迁移到 `resources.files.detail.csv_file: {...}` 形态

### Requirement: CSV outputs MUST bind via `outputs[*].to.file` and `outputs[*].write`
系统 MUST 要求 CSV 输出通过统一 target model 绑定:

- `outputs[*].to.file` MUST 为非空字符串
- `outputs[*].write.include_header` MAY 存在,默认 `true`
- `outputs[*].write.header_fields_output_by` MAY 存在,默认 `name`
- CSV 输出 MUST NOT 再使用 `outputs[*].container`

#### Scenario: csv output binds through to.file
- **WHEN** output 声明 `to.file=detail_csv`
- **AND** `resources.files.detail_csv.csv_file.path=./out`
- **THEN** 该 output MUST 绑定到对应文件资源

### Requirement: workflow MUST merge `resources.files` with the same precedence model as books
系统 MUST 对 `files` 资源采用与 `books` 相同的 merge precedence:

1. demand YAML 的 `resources.files`
2. workflow YAML 的 `workflow.resources.files`
3. Python overrides 的 `overrides.resources.files`

#### Scenario: workflow overrides demand file path
- **GIVEN** demand 声明 `resources.files.detail: {csv_file: {path: ./out/a}}`
- **AND** workflow 声明 `workflow.resources.files.detail: {csv_file: {path: ./out/b}}`
- **WHEN** workflow 运行该 demand
- **THEN** effective file path MUST 等于 workflow 声明值
