## ADDED Requirements

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

