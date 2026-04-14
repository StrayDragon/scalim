# yaml-dsl-lsp-server (delta) Specification

## ADDED Requirements

### Requirement: Go to Definition MUST support `workflow.runs[*].demand` paths statically

系统 MUST 在 workflow YAML 中为 `workflow.runs[*].demand` 字段提供 go-to-definition，并且解析 MUST 为静态解析（不执行用户代码、不 shell-out CLI）：

- 当光标位于 `workflow.runs[*].demand` 的字符串值范围内时，server MUST 返回指向目标 demand YAML 文件的 `Location`（至少 1 个）。
- demand path 解析规则 MUST 与 runtime 一致：
  - 相对路径 MUST 以 workflow YAML 文件所在目录为基准；
  - `@/...` 与 `ALIAS:/...` MUST 作为 path alias 语法被识别（在 alias 可解析时）。
- 解析 MUST 受 editor discovery 的 allowed roots 约束；若 demand path 解析后越界（path escapes allowed roots），server MUST 返回空结果。
- 任意解析失败（未知 alias、不存在/不可读、解析异常等）server MUST 返回空结果且不得 crash。

#### Scenario: relative demand path jumps to the referenced demand YAML file
- **GIVEN** 一个 workflow YAML 文件位于 `/repo/workflows/wf.yaml`
- **AND** 其中存在 `workflow.runs[*].demand: ./demands/d10_paid_orders.demand.yaml`
- **WHEN** 用户在该字符串值内触发 go-to-definition
- **THEN** server MUST 返回一个指向 `/repo/workflows/demands/d10_paid_orders.demand.yaml` 的 location

#### Scenario: alias demand path jumps when alias is configured
- **GIVEN** project discovery 可解析到 alias `@`（例如来自 `scalim.yaml` 的 import roots alias）
- **AND** workflow 中存在 `workflow.runs[*].demand: @/demands/d10_paid_orders.demand.yaml`
- **WHEN** 用户在该字符串值内触发 go-to-definition
- **THEN** server MUST 返回一个指向 alias 解析后目标文件的 location

#### Scenario: invalid or out-of-roots demand path yields empty definition result
- **GIVEN** 一个 workflow YAML 的某个 run 的 `demand` 路径无法解析或解析后越界
- **WHEN** 用户触发 go-to-definition
- **THEN** server MUST 返回空结果（不返回任何 location）
