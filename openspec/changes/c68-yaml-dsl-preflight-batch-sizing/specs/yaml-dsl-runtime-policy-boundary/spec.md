# yaml-dsl-runtime-policy-boundary (delta) Specification

## MODIFIED Requirements

### Requirement: demand runtime-policy fields MUST move out of YAML mainline

demand 侧明显属于 runtime policy 的字段 MUST 从 YAML 主线迁出到 Python / CLI runtime entrypoints:

- `guardrails.*` MUST 迁出 YAML
- `retry.*` MUST 迁出 YAML
- `batch_size` MUST 迁出 YAML(作为 runtime policy 不允许在 YAML 主线 authoring)
- demand `failure_policy` MUST 迁出 YAML
- `include_full_error_message` MUST 迁出 YAML
- `validate_unique_field_names` MUST 迁出 YAML

**Note:** 本要求约束的是 “runtime policy 的主线 authoring surface”。系统 MUST NOT 把 `batch_size` 等 runtime policy 重新引入 YAML authoring；若需要在运行时推导 derived 值,应通过 runtime entrypoints 的 typed surface（例如 hooks）实现,并保持调用方显式控制优先级最高。

#### Scenario: demand runtime-policy fields in YAML are rejected with migration guidance
- **GIVEN** 某个 demand YAML 仍声明 `include_full_error_message` 或 `validate_unique_field_names` 或顶层 `batch_size`
- **WHEN** 用户执行 validate 或运行入口解析
- **THEN** 系统 MUST 拒绝其作为主线 authoring 字段
- **AND** MUST 给出迁移到 runtime entrypoint 的提示

#### Scenario: runtime policy declarations remain rejected in YAML
- **GIVEN** 某个 demand YAML 试图声明顶层 `batch_size` 或其它 runtime policy 字段
- **WHEN** 用户执行 validate 或运行入口解析
- **THEN** 系统 MUST 拒绝其作为主线 authoring 字段
- **AND** MUST 给出迁移到 runtime entrypoint 的提示

## ADDED Requirements

### Requirement: derived runtime policy MUST NOT reduce caller control

当系统通过 runtime hooks 推导 derived runtime policy（例如 derived `batch_size`）时,系统 MUST 保持调用方的显式 runtime policy 具有最高优先级:

- 调用方显式提供 `RunOptions(batch_size=<int|None>)` 时,系统 MUST 使用显式值且 MUST 跳过 `pre_use_batch_size` policy signal。
- workflow per-run patch 显式提供 `batch_size=<int|None>` 时,系统 MUST 使用 patch 值且 MUST 跳过 `pre_use_batch_size` policy signal。

#### Scenario: explicit batch_size wins over policy signal
- **WHEN** 调用方显式传入 `RunOptions(batch_size=8000)`
- **THEN** effective `batch_size` MUST 为 `8000`
- **AND** 系统 MUST NOT 发射 `pre_use_batch_size` policy signal
