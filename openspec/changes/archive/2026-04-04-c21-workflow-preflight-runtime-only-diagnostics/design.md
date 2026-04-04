## Context

当前 workflow lifecycle（以 `scalim.dsl.by_yaml.run_workflow` 为代表）大致分层为：

- **workflow YAML parse**：解析 workflow YAML
- **workflow compile / preload**：`compile_workflow_ir(...)` 结构编译（会预加载 demand YAML 做 outputs/resources/deps wiring）
- **runtime policy merge**：构造 `RunOptions`，合并 `overrides` 与 `run_patches_by_id`（形成 per-run effective policy/overrides）
- **workflow engine execute**：进入 workflow engine 调度，每个 run 在执行前走 demand runtime compile / build_request

`validate_unique_field_names` 属于 runtime-only diagnostics policy（已从 YAML 主线迁出），但由于 `DemandConfig.validate_unique_field_names` 默认值为 `True`，在 workflow compile/preload 阶段被错误消费会导致“抢跑 fail-fast”。0.7.4 / 0.7.5 通过在 preload loader 上 hard-disable 规避了该问题，但 duplicate-name 的报错仍然会被延迟到节点执行阶段。

## Goals / Non-Goals

**Goals:**
- 在 `run_workflow(...)` 中引入一个 **workflow preflight** 阶段：在进入 engine 调度之前，基于 per-run effective policy/overrides 运行一组“runtime-only 但可推理”的诊断。
- v1 仅落地一个明确的 check：`validate_unique_field_names`（duplicate effective field display names）。
- preflight 发现问题时 **直接 raise** 中止整个 workflow（fail-fast，且不与 `failure_policy` 交织）。
- preflight 必须基于 **effective config** 口径运行（YAML → overrides → per-run patch 合并后），避免误报/漏报。
- 为长期可维护性提供一个很小的 preflight 框架：check registry + context + 单 check 的可扩展结构。

**Non-Goals:**
- 不在本变更中把所有 runtime compile 错误都“前移为 workflow compile error”。仅把明确的、inferable 的诊断前移。
- 不修改 `compile_workflow_ir(...)` 的返回结构（保持其对外/对内契约稳定）。
- 不新增 OpenSpec docs-site 生成物/注入区块，不涉及 `*.gen.*` 文件编辑。

## Decisions

### Decision: preflight 的插入点

将 preflight 插入到 `run_workflow(...)` 内部：

1) workflow compile/preload 完成后（`compile_workflow_ir(...)` + `derive_cache_pool_consumers(...)`）
2) `RunOptions`/`run_patches_by_id`/`overrides` 合并完成，具备 per-run effective policy/overrides
3) **在调用 workflow engine（`run_workflow_ir(...)`）之前**

这样能确保：
- 不在 preload 阶段抢跑 runtime-only policy
- 能正确读取 override 后的 outputs/resources（有效口径）

### Decision: 失败语义

preflight 一旦发现错误：
- 直接 raise（workflow 整体失败）
- fail-fast：按 workflow.runs 声明顺序检查，第一个错误立即抛出
- 不尝试把 preflight 结果融合到 `failure_policy!=all_fail` 的调度/取消逻辑（避免实现复杂度与长期维护成本）

### Decision: v1 覆盖范围（明确收敛）

v1 仅做：
- `validate_unique_field_names`（duplicate effective field display names）在满足触发条件时的提前诊断

其它 runtime-only 但可推理 diagnostics 后续再按 checklist 扩展（本变更只提供框架与第一个 check）。

### Decision: preflight 框架形态

引入一个小框架：
- `WorkflowPreflightContext`: 提供 workflow 运行所需的最小上下文（workflow 路径、runs、template_vars/allowed_yaml_roots、base options、workflow resources override、run patches 等）
- `WorkflowPreflightCheck` 协议/接口：`check_id` + `run(ctx) -> None`
- 一个 check registry 列表：`WORKFLOW_PREFLIGHT_CHECKS = [...]`

v1 check 采用“只做必要计算”的策略：
- 仅在 per-run effective `validate_unique_field_names=True` 的情况下加载 demand config 并做名字去重诊断
- 严格按 effective outputs/resources 判断触发条件（避免 override 后不应触发却误报）

## Risks / Trade-offs

- [行为变化] `failure_policy=primary_only` 下，duplicate-name 不再作为“单 run 错误”返回，而是 preflight 直接中止整个 workflow → 通过 specs + tests 明确这是设计选择。
- [性能] preflight 需要在 engine 前对部分 runs 重新 load demand YAML（compile/preload 阶段已加载过一次） → v1 只在 policy 触发时执行；后续可考虑缓存/复用，但不在本变更范围。
- [口径一致性] overrides.outputs 解析若过度复用 runtime compile 逻辑，可能引入额外的 validation side effects → v1 check 只解析 header 相关信息，并在遇到非本 check 的解析错误时选择跳过该 check（避免把其它错误提前提升为全局失败）。

