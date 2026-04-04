# workflow-preflight-runtime-only-diagnostics Specification

**状态: ✅ 已实现**

## Purpose
为 `run_workflow(...)` 增加一个 engine 执行前的 preflight 阶段,用于运行一组“runtime-only 但可推理”的诊断（v1 仅覆盖 `validate_unique_field_names`）,并以 fail-fast 的方式把错误提前暴露为 workflow compile/config error。

## Related Code (as implemented)
- `src/IMPL_ROOT/dsl/by_yaml/workflow_entrypoints.py` (preflight 插入点)
- `src/IMPL_ROOT/dsl/by_yaml/workflow_preflight.py` (preflight 框架 + v1 check)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/compiler.py` (YAML 层抢跑防护: overrides 存在时禁用 YAML precheck)

## Requirements

### Requirement: workflow preflight MUST run after effective policy merge but before workflow engine execution
系统 MUST 在进入 workflow engine 调度前运行 workflow preflight:

- **MUST** 在 workflow compile/preload（结构预加载）完成之后运行
- **MUST** 在 per-run patches 与 overrides 合并完成、具备 effective policy/outputs/resources 口径之后运行
- **MUST** 在 workflow engine（调度/执行）启动之前运行

#### Scenario: preflight failure stops workflow before engine
- **GIVEN** workflow 存在某个可推理的 preflight 失败
- **WHEN** 用户调用 `run_workflow(...)`
- **THEN** 系统 MUST 直接 raise 并中止整个 workflow
- **AND** workflow engine MUST NOT 被启动（不得继续调度其它 runs）

### Requirement: preflight v1 MUST reject duplicate effective field display names when validate_unique_field_names is enabled and outputs require name headers
当满足以下条件时,系统 MUST 在 preflight 阶段拒绝 duplicate effective field display names:

- `validate_unique_field_names=True`（runtime policy / per-run patch 的 effective 值）
- effective outputs 中存在需要 `header_fields_output_by=name` 且会写 header 的输出

#### Scenario: duplicate effective field display names fail fast in preflight
- **GIVEN** 某个 workflow run 的 demand fields 存在 duplicate effective field display names
- **AND** 该 run 的 effective `validate_unique_field_names=True`
- **AND** 该 run 的 effective outputs 会写入 `header_fields_output_by=name` 的 header
- **WHEN** 用户调用 `run_workflow(...)`
- **THEN** 系统 MUST 在进入 engine 调度前 fail-fast 抛出错误
- **AND** 错误信息 MUST 包含 run id 与 demand 路径

#### Scenario: validate_unique_field_names disabled by per-run patch skips preflight rejection
- **GIVEN** workflow run A 的 demand fields 存在 duplicate effective field display names
- **AND** `run_patches_by_id["A"].demand_diagnostics.validate_unique_field_names=false`
- **WHEN** 用户调用 `run_workflow(...)`
- **THEN** 系统 MUST NOT 因该诊断在 preflight 阶段失败

