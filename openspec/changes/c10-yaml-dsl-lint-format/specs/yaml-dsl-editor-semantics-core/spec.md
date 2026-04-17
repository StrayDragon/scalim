# yaml-dsl-editor-semantics-core (delta) Specification

## MODIFIED Requirements

### Requirement: Editor semantics core MUST support extracting Python references by cursor position
系统 MUST 提供一个基于 `yaml_text + position` 的抽取能力，用于把编辑器光标映射到 YAML DSL 内的 Python 引用字段。

抽取结果 MUST 至少包含：

- 命中的 YAML 字段路径（canonical dot path）
- 命中的 Python 引用字符串（raw value 或经 `call_by` 头部解析后的 reference）
- 命中范围 `range`（以 1-based 表示，供 server 转换为 LSP range）
- 失败时的可诊断 warnings（不得抛出未捕获异常）

支持字段集合 v1 MUST 至少覆盖：

- `loader`
- `call_by`
- `retry.should_retry`（包含常见嵌套路径下的该字段）

当上述字段的 scalar 为 YAML block scalar（`|`/`>` 及其变体）且跨多行时：

- 抽取 MUST 仍然可用
- 返回的 `range` MUST 精确覆盖“光标所在行内”的命中 token（不得要求用一个跨行 range 覆盖整个 block）

#### Scenario: cursor inside a scalar string yields extracted reference + range
- **GIVEN** 某 demand YAML 包含 `loader: "pkg.mod:func"` 且光标位于该字符串值内部
- **WHEN** editor semantics core 执行光标抽取
- **THEN** MUST 返回 `yaml_path` 指向该字段
- **AND** MUST 返回 `reference` 等于 `pkg.mod:func`
- **AND** MUST 返回的 `range` MUST 精确覆盖该 reference 的文本范围

#### Scenario: cursor inside a block scalar yields extracted reference + range
- **GIVEN** 某 demand YAML 包含：
  - `call_by: |`
  - `  pkg.mod:fn(a=1)`
- **WHEN** 光标位于 `pkg.mod:fn` 区间并触发抽取
- **THEN** MUST 返回 `reference` 等于 `pkg.mod:fn`
- **AND** 返回的 `range` MUST 仅覆盖光标所在行内的 `pkg.mod:fn`（不得包含参数段）

#### Scenario: call_by reference with args yields head reference
- **GIVEN** 某 demand YAML 包含 `call_by: "pkg.mod:fn(a=1)"` 且光标位于 `pkg.mod:fn` 区间
- **WHEN** editor semantics core 执行光标抽取
- **THEN** MUST 返回 `reference` 等于 `pkg.mod:fn`
- **AND** 返回的 `range` MUST 覆盖 `pkg.mod:fn`（不得包含参数段）

#### Scenario: parse failure degrades to empty result with warnings
- **GIVEN** 某 YAML 语法不完整或无法被解析
- **WHEN** editor semantics core 执行光标抽取
- **THEN** MUST 返回空结果
- **AND** MUST 提供至少一条 warning 用于排障

### Requirement: Editor semantics core MUST extract field-id tokens from `call_by` kwargs value positions
系统 MUST 扩展光标抽取能力，使其能在 `call_by` 的参数段（`(...)`）内识别 kwargs 的 `=` **右侧** field-id token，并用于 editor/LSP 语义能力。

覆盖 callsite 至少包括：
- `fields.*.call_by`
- `outputs[*].aggregate.fields.*.call_by`
- builtin callable：`call_by: "^<id>(...)"`（head 为 builtin id）

抽取必须满足：

- 抽取 MUST 仅对 `=` 右侧生效；`=` 左侧 kwargs 名称 MUST NOT 被当作 field-id
- token 抽取 MUST 返回精确 range（仅覆盖 token 本身）
- 当值为空（例如 `x=` 或 `x= `）且用户触发 completion 时，抽取结果 MUST 能提供稳定的 value_range（用于 completion）
- 解析失败 MUST 降级为空结果 + warnings（不得抛出未捕获异常）
- 参数段解析 MUST 支持换行符与 Python 风格 `#` 注释（不在 string literal 内），以便 multiline `call_by`（含 YAML block scalar）仍可提供 token 抽取

#### Scenario: cursor on kwargs value token yields extracted field reference
- **GIVEN** YAML 包含 `call_by: "pkg.mod:fn(x=a)"`
- **WHEN** 光标位于 `a` 上并触发 hover/definition
- **THEN** 抽取结果 MUST 将 token `a` 解析为字段引用
- **AND** MUST 返回仅覆盖 `a` 的 range

#### Scenario: cursor on kwargs value token in multiline call_by yields extracted field reference
- **GIVEN** YAML 包含：
  - `call_by: |`
  - `  pkg.mod:fn(`
  - `    x=a, # comment`
  - `  )`
- **WHEN** 光标位于 `a` 上并触发 hover/definition
- **THEN** 抽取结果 MUST 将 token `a` 解析为字段引用
- **AND** MUST 返回仅覆盖 `a` 的 range

#### Scenario: cursor on kwargs name yields empty field extraction
- **GIVEN** YAML 包含 `call_by: "pkg.mod:fn(x=a)"`
- **WHEN** 光标位于 `x` 上并触发 hover/definition
- **THEN** 系统 MUST NOT 将 `x` 解析为字段引用
- **AND** MUST 返回空结果（允许包含 warnings）

