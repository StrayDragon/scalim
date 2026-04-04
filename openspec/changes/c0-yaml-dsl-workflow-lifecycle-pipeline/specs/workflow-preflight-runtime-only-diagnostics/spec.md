# workflow-preflight-runtime-only-diagnostics Specification

## ADDED Requirements

### Requirement: preflight checks MUST be managed as an explicit registry of inferable diagnostics
为避免 scope creep 与入口遗漏，系统 MUST 将 workflow preflight 的检查项管理为显式 registry（SSOT 清单），并保证其中每个检查都满足“可推理子集”约束：

- check MUST NOT 依赖 `$ctx` 或 init_vars 渲染结果
- check MUST NOT 依赖外部运行态（例如文件是否存在、sheet 是否存在）
- check MUST 仅消费 structural preload 的结果 + per-run effective policy/outputs/resources 口径

#### Scenario: only checks in the registry are executed during preflight
- **GIVEN** workflow preflight 存在一个显式的 checks registry（清单）
- **WHEN** 用户调用 `run_workflow(...)` 且触发 preflight
- **THEN** 系统 MUST 仅执行 registry 中登记的 checks
- **AND** 不在 registry 中的 diagnostics MUST NOT 在 preflight 阶段被隐式执行

### Requirement: preflight MUST consume structural preload results and MUST NOT reload demand YAML
为减少入口分歧与避免“preload/compile 与 preflight 各自重新解析 demand YAML”带来的 drift，系统 MUST 让 preflight 消费 structural preload 的结果（例如已解析的 `DemandConfig`），并且 MUST NOT 在 preflight 阶段再次读取/解析 demand YAML 文件。

#### Scenario: preflight does not perform demand YAML IO
- **GIVEN** workflow structural preload 已获得某个 run 的 demand 结构信息
- **WHEN** 系统进入 preflight 阶段
- **THEN** preflight MUST 仅消费 preload 结果与 effective policy/overrides 口径
- **AND** MUST NOT 再次读取/解析该 run 的 demand YAML
