# yaml-dsl-lsp-notebooks-regression Specification (Delta)

## ADDED Requirements

### Requirement: Notebooks regression suite MUST cover aggregate field references
系统 MUST 从 notebooks fixtures 中抽取 `outputs[*].aggregate` 相关的字段引用点（包括 group_by/metric field refs/rank refs/score_by_rank），并对每个引用回归以下操作不得崩溃：

- completion（Ctrl+Space / 手动触发）
- definition
- hover

允许返回空结果，但 MUST 输出可诊断 warnings（如解析失败原因）。

#### Scenario: aggregate field operations degrade gracefully
- **GIVEN** fixtures YAML 中存在 `outputs[*].aggregate` 且包含至少一个 field-id 引用点
- **WHEN** 回归套件对该引用执行 completion/definition/hover
- **THEN** 测试 MUST 通过且进程不得崩溃
