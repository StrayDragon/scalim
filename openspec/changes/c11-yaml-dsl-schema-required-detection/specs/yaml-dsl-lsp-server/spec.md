## ADDED Requirements

### Requirement: LSP server MUST avoid polluting non-DSL YAML documents
系统 MUST 在提供 YAML DSL 语义能力前进行 DSL 探测,并满足:

- 对非 DSL YAML,server MUST 发布空 diagnostics
- 对非 DSL YAML,server MUST 对 go-to-definition/hover/completion 返回空结果(不得 crash)
- DSL 探测 MUST 优先依据 schema 顶层 required:
  - 当 YAML 根 mapping 包含键 `workflow` 且其值为 mapping 时,该文件 MUST 被视为 workflow DSL
  - 当 YAML 根 mapping 同时包含键 `name` 与 `main_source` 时,该文件 MUST 被视为 demand DSL
- 当 required 未满足时,server MAY 使用 DSL 专属语法特征作为 permissive fallback（例如 `$import/$init_var`、`loader/call_by`、schema modeline 指向 scalim schema）

#### Scenario: unrelated YAML produces no diagnostics
- **GIVEN** 某 YAML 不满足 schema(required) 且不包含 DSL 专属语法特征
- **WHEN** client 请求 diagnostics
- **THEN** server MUST 返回空 diagnostics

#### Scenario: in-progress DSL YAML still enables editor semantics via fallback
- **GIVEN** 某 YAML 尚未写全 required 字段
- **AND** 其文本包含 DSL 专属语法特征（例如 `loader:` 或 `$import`）
- **WHEN** 用户触发 go-to-definition
- **THEN** server SHOULD 尽最大努力返回可解析的定义位置,失败时 MUST 返回空结果且包含可诊断 warnings

