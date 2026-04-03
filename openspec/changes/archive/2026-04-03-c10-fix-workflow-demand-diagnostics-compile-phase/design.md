## Context

`validate_unique_field_names` 已从 demand YAML 主线移出，当前契约要求该诊断只通过 runtime entrypoints 控制：全局使用 `DemandDiagnosticsPolicy`，workflow per-run 使用 `DemandDiagnosticsOverride`。但 workflow IR 编译阶段会先调用 `_load_demands()` 读取所有 demand YAML，而这一步直接走 `YamlDemandLoader.load(..., validate_unique_field_names=True)` 的默认值，导致 runtime policy 还未进入编译链路前就发生 fail-fast。

该问题跨越 `workflow_compile.py`、`workflow_entrypoints.py` 与 runtime compiler 行为边界，但不涉及 schema、生成物或 injected blocks。所有变更都应保持手工维护；不修改任何 `.gen.` 文件。漂移门禁以 `openspec validate --all --strict --no-interactive`、相关 pytest 与最终 `just openspec-check`/`just qa` 为准。

## Goals / Non-Goals

**Goals:**
- 让 workflow compile 阶段的 demand 预加载只承担结构分析职责，不抢跑 runtime-only duplicate display name 校验。
- 保持 standalone demand compile 与 workflow 阶段 4 的 demand compile 继续尊重 `DemandDiagnosticsPolicy` / `DemandDiagnosticsOverride`。
- 为全局 policy 与 per-run patch 各补一条 workflow 回归测试，防止问题回归。

**Non-Goals:**
- 不重新引入 demand YAML 顶层 `validate_unique_field_names` authoring surface。
- 不新增新的 workflow runtime 参数或 CLI surface。
- 不顺手调整其它 demand diagnostics 语义或 unrelated workflow compile 逻辑。

## Decisions

### 1. Workflow compile 预加载固定关闭 `validate_unique_field_names`

采用“结构预加载”和“运行期诊断”分层方案：`_load_demands()` 在 workflow IR 编译阶段始终以 `validate_unique_field_names=False` 加载 demand YAML。这样阶段 1 只负责拿到 outputs/resources 等结构信息，不承担 runtime policy 决策。

选择理由：
- 直接匹配当前架构意图：duplicate display name 属于 runtime diagnostics，不属于 workflow graph/build resources 所需的结构合法性。
- 同时覆盖全局 `demand_diagnostics` 与 per-run `run_patches_by_id` 场景，无需把 per-run patch 合并逻辑提前搬进 IR 编译。
- 改动面最小，不扩散 `compile_workflow_ir(...)` 的签名和调用链。

替代方案对比：
- 传递全局 `demand_diagnostics` 到 `compile_workflow_ir(...)`：只能解决全局 policy，无法自然解决 per-run override。
- 在阶段 1 逐 run 合并 `run_patches_by_id`：语义完整但会把 runtime patch 合并逻辑提前耦合到 IR compile，复杂度与维护成本不成比例。

### 2. 阶段 4 继续作为 duplicate-name 诊断唯一执行点

保留 `runtime/compiler.py` 的现有行为不变：真正的 duplicate display name 校验仍由 `compiler.compile()` 根据 effective `RunOptions.demand_diagnostics` 决定。这样 standalone demand compile 与 workflow demand compile 共享同一诊断边界。

### 3. 通过 workflow 级测试锁定行为边界

新增两类测试：
- `compile_workflow_ir(...)` 在 duplicate display names demand 上不应提前失败。
- `run_workflow(...)` 在全局 `DemandDiagnosticsPolicy(validate_unique_field_names=False)` 与 per-run `WorkflowRunPatch(demand_diagnostics=DemandDiagnosticsOverride(validate_unique_field_names=False))` 下都应成功运行。

## Risks / Trade-offs

- [风险] 阶段 1 不再提前发现 duplicate display name，错误会推迟到阶段 4 才暴露。 → 缓解：这正是 runtime policy boundary 的目标；默认策略仍会在阶段 4 fail-fast，只是位置后移到真正具备 policy 信息的边界。
- [风险] workflow compile 测试 fixture 若过度依赖现有 helper，可能引入不必要的 I/O 噪音。 → 缓解：复用现有 workflow test helpers，保持最小 YAML fixture。
- [风险] 后续若新增其它 runtime-only diagnostics，阶段 1 可能再次误用 loader 默认值。 → 缓解：在 spec 中明确“workflow compile 预加载是结构性加载”，为后续评审提供准绳。

## Migration Plan

- 实现 `_load_demands()` 的固定关闭策略，并保留现有错误包装。
- 补充 workflow compile / run_workflow 回归测试。
- 更新 OpenSpec delta specs，确保运行时策略边界与 workflow run patches 的行为被文档化。
- 验证目标测试与 OpenSpec 校验通过；如需回滚，仅恢复 `_load_demands()` 的调用参数与新增测试/工件。

## Open Questions

- 无。当前问题边界和修复方向已足够明确，不需要新增 API 或额外 authoring surface。
