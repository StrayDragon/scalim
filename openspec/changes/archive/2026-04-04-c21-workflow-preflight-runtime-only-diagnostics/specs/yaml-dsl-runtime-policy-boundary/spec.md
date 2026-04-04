# yaml-dsl-runtime-policy-boundary Specification

## ADDED Requirements

### Requirement: workflow MUST run inferable runtime-only diagnostics at the effective-policy boundary (preflight)
当 workflow 具备 per-run effective runtime policy（包括 run patches）以及 effective outputs/resources 口径后，系统 MUST 在进入 engine 调度前运行一组 inferable diagnostics（workflow preflight）。

该机制 MUST 满足：
- diagnostics MUST NOT 在 workflow compile/preload 阶段抢跑
- diagnostics MUST 基于 effective policy/overrides 口径（避免 YAML 与 override 口径不一致导致误报/漏报）

#### Scenario: preload stays structural but preflight may reject duplicates
- **GIVEN** 某个 workflow run 引用的 demand YAML 含有 duplicate effective field display names
- **WHEN** 系统执行 workflow compile/preload 阶段的结构预加载（例如 `compile_workflow_ir(...)`）
- **THEN** 系统 MUST NOT 因该诊断直接失败
- **AND** 在具备 effective runtime policy 的 workflow preflight 边界上，系统 MAY 进一步决定是否报错
