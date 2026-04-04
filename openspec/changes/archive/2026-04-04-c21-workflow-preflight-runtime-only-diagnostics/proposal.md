## Why

0.7.4 / 0.7.5 对 `validate_unique_field_names` 的 bug 做了“编译/预加载阶段 hard-disable”的修复，避免 workflow compile/preload 抢跑 runtime-only diagnostics。

但这仍然是一个 workaround：当 `validate_unique_field_names=True` 且输出需要 `header_fields_output_by=name` 时，duplicate effective field display names 的错误会被延迟到节点真正执行/编译时才暴露（尤其在 `failure_policy=primary_only` 的工作流中更难定位）。

我们希望把这类“runtime-only 但可推理”的诊断前移到 workflow 执行前的一个 preflight 阶段，使用户在进入调度/执行之前就能得到明确、可读、fail-fast 的错误。

## What Changes

- 在 `run_workflow(...)` 中引入一个 policy-aware 的 workflow preflight 阶段：
  - 运行时机：在 workflow compile/preload 之后、进入 workflow engine 调度之前
  - 语义：发现 preflight 失败则 **直接 raise**，中止整个 workflow（不与 `failure_policy` 交织）
  - 口径：必须基于 **effective config**（YAML → overrides → per-run patch/merge 后的结构）进行判断，避免误报/漏报
- v1 仅覆盖一个明确的 inferable check：`validate_unique_field_names`（duplicate effective field display names）
- 保留现有 compile/preload 阶段的 hard-disable（继续确保 runtime policy 不会在 preload 阶段被提前消费）

## Capabilities

### New Capabilities
- `workflow-preflight-runtime-only-diagnostics`: 在 workflow engine 启动前运行一组“runtime-only 但可推理”的诊断，fail-fast 报错。

### Modified Capabilities
- `yaml-dsl-workflow`: 明确 workflow lifecycle 中 preflight 的插入点与失败语义，并保证 overrides/patch 口径一致。
- `yaml-dsl-runtime-policy-boundary`: 明确 runtime-only diagnostics 的“最早允许生效边界”从“节点 runtime compile”扩展为“workflow preflight（具备 effective policy 之后）”。

## Impact

- 影响 `scalim.dsl.by_yaml.run_workflow` 的错误暴露时机：duplicate-name 等 inferable 诊断会在 engine 调度前失败，而不是延迟到节点执行阶段。
- 预期改动代码集中在 `src/scalim/dsl/by_yaml/workflow_entrypoints.py`，并新增一个小型的 preflight 框架模块用于长期扩展。
- 需要补充/调整 workflow 相关测试（尤其是 `failure_policy=primary_only` 下的 duplicate-name 行为将变为“compile error”）。

