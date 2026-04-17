# workflow-cache-pool (delta)

## MODIFIED Requirements

### Requirement: workflow options expose a stable `cache_pool` configuration (replacing `share_preload_cache`)

系统 MUST 将 workflow cache pool 的配置入口收敛到 runtime policy boundary（`workflow_runtime_options.cache_pool`），并保持对外配置面受限（preset-based）：

- workflow YAML MUST NOT 再接受 `workflow.options.cache_pool`（出现时 MUST fail-fast 并给出迁移指引）
- 系统 MUST 提供封闭集合的 cache_pool preset（示例）：
  - `WorkflowCachePoolDisabled()`（默认）
  - `WorkflowCachePoolPreloadForeverUnlimited()`
  - `WorkflowCachePoolPreloadForeverShared(max_entries=<positive-int>, pin=...)`
- `WorkflowCachePoolPreloadForeverShared` 仅允许暴露最小 knobs（bounded + pin）：
  - `max_entries` MUST 为正整数，且 MUST 显式提供（无隐式默认值）。**BREAKING**
  - `pin` MAY 存在，用于在 bounded 场景中将指定 logical keys 常驻到 workflow_end（避免 refcount 自动释放）
- `WorkflowCachePoolPreloadForeverUnlimited` MUST 不暴露 budget/pin knobs，并且其语义 MUST 等价于：
  - `release_policy=workflow_end`（不启用 DAG refcount 自动释放）
  - 禁用 entries 数量预算检查（不强制 `max_entries` 预算护栏）
- 其余策略 MUST 固定为稳定默认（不对外暴露 knobs），例如：
  - `conflict_policy=error`
  - bounded preset: `release_policy=dag_refcount`
  - bounded preset: `budget.over_budget_policy=fail_fast`
- 旧的 `workflow.options.share_preload_cache` MUST 被拒绝（提示迁移到 `workflow_runtime_options.cache_pool` preset）

#### Scenario: cache_pool config in YAML is rejected with migration guidance
- **GIVEN** workflow YAML 包含 `workflow.options.cache_pool`
- **WHEN** 用户执行 validate/compile 或运行入口解析
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 指向 runtime entrypoints（例如 `run_workflow(..., workflow_runtime_options=...)`）

#### Scenario: cache_pool is enabled through unlimited runtime preset
- **GIVEN** 调用方传入 `workflow_runtime_options.cache_pool=WorkflowCachePoolPreloadForeverUnlimited()`
- **WHEN** 用户执行 `run_workflow(...)`
- **THEN** 系统 MUST 启用跨 nodes 的 `preload_forever` 共享
- **AND** cache entries MUST 常驻到 workflow_end（不得在 workflow 中途因 refcount 归零而自动释放）
- **AND** 系统 MUST NOT 按 entries 数量预算对 cache pool 施加上限

#### Scenario: cache_pool is enabled through bounded runtime preset
- **GIVEN** 调用方传入 `workflow_runtime_options.cache_pool=WorkflowCachePoolPreloadForeverShared(max_entries=16)`
- **WHEN** 用户执行 `run_workflow(...)`
- **THEN** 系统 MUST 启用跨 nodes 的 `preload_forever` 共享
- **AND** MUST 按 `max_entries` 预算限制 cache entries 数量

#### Scenario: bounded preset supports pin for selected logical keys
- **GIVEN** 调用方传入 `WorkflowCachePoolPreloadForeverShared(max_entries=16, pin=(WorkflowCachePoolPin(kind=\"preload_forever\", source_id=\"s1\"),))`
- **WHEN** `s1` 的缓存条目 refcount 归零
- **THEN** 系统 MUST NOT 释放该条目（等价常驻到 workflow_end）
