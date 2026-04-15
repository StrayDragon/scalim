# workflow-cache-pool (delta) Specification

## MODIFIED Requirements

### Requirement: workflow options expose a stable `cache_pool` configuration (replacing `share_preload_cache`)
系统 MUST 将 workflow cache pool 的配置入口收敛到 runtime policy boundary（`workflow_runtime.cache_pool`），并保持对外配置面受限（preset-based）：

- workflow YAML MUST NOT 再接受 `workflow.options.cache_pool`（出现时 MUST fail-fast 并给出迁移指引）
- 系统 MUST 提供封闭集合的 cache_pool preset（示例）：
  - `WorkflowCachePoolDisabled()`（默认）
  - `WorkflowCachePoolPreloadForeverShared(max_entries=16)`
- `WorkflowCachePoolPreloadForeverShared` 仅允许暴露最小 knobs：
  - `max_entries` MUST 为正整数（默认 16）
- 其余策略 MUST 固定为稳定默认（不对外暴露 knobs），例如：
  - `conflict_policy=error`
  - `release_policy=dag_refcount`
  - `budget.over_budget_policy=fail_fast`
  - `pin` 暂不对外开放（如出现明确需求，MUST 以新增 preset 的方式扩展）
- 旧的 `workflow.options.share_preload_cache` MUST 被拒绝（提示迁移到 `workflow_runtime.cache_pool` preset）

#### Scenario: cache_pool config in YAML is rejected with migration guidance
- **GIVEN** workflow YAML 包含 `workflow.options.cache_pool`
- **WHEN** 用户执行 validate/compile 或运行入口解析
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 指向 runtime entrypoints（例如 `run_workflow(..., workflow_runtime=...)`）

#### Scenario: cache_pool is enabled through runtime preset
- **GIVEN** 调用方传入 `workflow_runtime.cache_pool=WorkflowCachePoolPreloadForeverShared(max_entries=16)`
- **WHEN** 用户执行 `run_workflow(...)`
- **THEN** 系统 MUST 启用跨 nodes 的 `preload_forever` 共享
- **AND** MUST 按 `max_entries` 预算限制 cache entries 数量
