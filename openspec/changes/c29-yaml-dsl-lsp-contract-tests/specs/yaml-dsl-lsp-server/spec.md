## MODIFIED Requirements

### Requirement: YAML DSL LSP server MUST keep user-facing behavior stable via contract tests

YAML DSL LSP server 的用户侧行为（diagnostics、definition/hover/completion、code actions）在重构前后 MUST 保持稳定，且该稳定性 MUST 由协议级 contract tests 覆盖。

#### Scenario: definition/hover/completion baseline is preserved

- **GIVEN** 一个包含 imports 与内联 Python reference 的 YAML workspace
- **AND** 该 workspace 在 baseline 版本上能得到预期的 definition/hover/completion 结果
- **WHEN** 进行内部重构（不改变对外行为）
- **THEN** 运行 LSP contract tests MUST 仍然通过（同一组 fixtures 与断言）
