# yaml-dsl-workflow-validate Specification

## Purpose
TBD - created by archiving change c12-yaml-dsl-workflow-validate-cli. Update Purpose after archive.
## Requirements
### Requirement: CLI MUST provide workflow-level validate that recursively validates referenced demands
系统 MUST 提供一个面向 CI/预发布的 workflow-level validate CLI 入口，用于在不执行 workflow 的前提下，对 workflow YAML 及其引用的 demands 做静态/编译期校验。

该入口 MUST 支持形如：

- `scalim-cli yaml-dsl validate --type workflow <workflow.yaml>`

校验范围 MUST 至少包含：

- workflow YAML 自身结构与语义校验（解析、引用合法性、cycle detection 等）
- 递归校验每个 `runs[*].demand` 引用的 demand YAML（允许 imports/$import，并在错误中提供可诊断的引用链路）
- workflow ↔ demand 的交叉一致性校验（例如 `writes[*]` 引用的 output id 必须存在于对应 demand 的 outputs 中）

#### Scenario: validate fails when workflow writes reference a missing output id
- **GIVEN** workflow YAML 中某个 `runs[*].demand` 引用的 demand YAML 不包含 output `"missing_output"`
- **AND** workflow YAML 的 `runs[*].writes[*]` 引用了该 output `"missing_output"`
- **WHEN** 调用方执行 `scalim-cli yaml-dsl validate --type workflow <workflow.yaml>`
- **THEN** 校验 MUST 失败（非零退出码）
- **AND** 输出 MUST 提供可定位的诊断信息，指出对应的 `writes[*]` 引用无效

