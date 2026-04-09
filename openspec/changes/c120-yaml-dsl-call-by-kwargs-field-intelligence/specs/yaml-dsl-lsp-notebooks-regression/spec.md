# yaml-dsl-lsp-notebooks-regression Specification (Delta)

## ADDED Requirements

### Requirement: Notebooks regression suite MUST cover `call_by` kwargs value field intelligence
系统 MUST 在 notebooks fixtures 回归中，覆盖 `call_by: "pkg.mod:fn(x=a)"` 这类参数值引用字段的场景，并对每个被抽取到的 field-id token 回归以下操作不得崩溃：

- completion（Ctrl+Space / 手动触发）
- definition
- hover

允许返回空结果，但 MUST 输出可诊断 warnings（如解析失败原因）。

#### Scenario: call_by kwargs value operations degrade gracefully
- **GIVEN** fixtures YAML 中存在 `call_by` 且包含至少一个 kwargs 值 token
- **WHEN** 回归套件对该 token 执行 completion/definition/hover
- **THEN** 测试 MUST 通过且进程不得崩溃
