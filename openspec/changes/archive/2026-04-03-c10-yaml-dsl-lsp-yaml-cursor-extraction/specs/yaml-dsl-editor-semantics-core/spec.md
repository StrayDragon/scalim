## ADDED Requirements

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

#### Scenario: cursor inside a scalar string yields extracted reference + range
- **GIVEN** 某 demand YAML 包含 `loader: "pkg.mod:func"` 且光标位于该字符串值内部
- **WHEN** editor semantics core 执行光标抽取
- **THEN** MUST 返回 `yaml_path` 指向该字段
- **AND** MUST 返回 `reference` 等于 `pkg.mod:func`
- **AND** MUST 返回的 `range` MUST 精确覆盖该 reference 的文本范围

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

