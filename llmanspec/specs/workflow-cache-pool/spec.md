---
llman_spec_valid_scope:
  - src/scalim/
llman_spec_valid_commands:
  - llman sdd validate workflow-cache-pool --type spec --strict --no-interactive
llman_spec_evidence:
  - migrated from openspec
---

```toon
kind: llman.sdd.spec
name: "workflow-cache-pool"
purpose: "提供 workflow-scope 的缓存池(`cache_pool`),用于在同一次 workflow 执行内跨 nodes 复用可共享缓存条目(当前主要用于 `preload_forever` 结果),并通过 signature-based keys/冲突策略/生命周期(refcount+pin)/预算策略/观测事件/并发安全确保\"复用正确且可诊断\"."
requirements[1]{req_id,title,statement}:
  r1,workflow options expose a stable `cache_pool` configuration (replacing `share_pr,"系统 MUST 将 workflow cache pool 的配置入口收敛到 runtime policy boundary,并保持对外配置面受限（preset-based）： - workflow YAML MUST NOT 再接受 `workflow.options.cache_pool`（出现时 MUST fail-fast 并给出迁移指引） - 系统 MUST 提供封闭集合的 cache_pool preset： - `WorkflowCachePoolDisabled()`（默认） - `WorkflowCachePoolPreloadForeverUnlimited()` - `WorkflowCachePoolPreloadForeverShared(max_entries=<positive-int>, pin=...)` - `WorkflowCachePoolPreloadForeverShared` 仅允许暴露最小 knobs： - `max_entries` MUST 为正整数，且 MUST 显式提供（无隐式默认值）。 - `pin` MAY 存在，用于在 bounded 场景中将指定 logical keys 常驻到 workflow_end - `WorkflowCachePoolPreloadForeverUnlimited` MUST 不暴露 budget/pin knobs，并且其语义 MUST 等价于： - `release_policy=workflow_end`（不启用 DAG refcount 自动释放） - 禁用 entries 数量预算检查 - 其余策略 MUST 固定为稳定默认（不对外暴露 knobs），例如： - `conflict_policy=error` - bounded preset: `release_policy=dag_refcount` - bounded preset: `budget.over_budget_policy=fail_fast` - 旧的 `workflow.options.share_preload_cache` MUST 被拒绝（提示迁移到 cache_pool preset）"
scenarios[5]{req_id,id,given,when,then}:
  r1,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r1,"cache-pool-config-in-yaml-is-rejected-with-migration-guidanc",workflow YAML 包含 `workflow.options.cache_pool`,用户执行 validate/compile 或运行入口解析,"系统 MUST fail-fast"
  r1,"cache-pool-is-enabled-through-unlimited-runtime-preset",调用方传入 `workflow_runtime_options.cache_pool=WorkflowCachePoolPreloadForeverUnlimited()`,用户执行 `run_workflow(...)`,系统 MUST 启用跨 nodes 的 `preload_forever` 共享
  r1,"cache-pool-is-enabled-through-bounded-runtime-preset",调用方传入 `workflow_runtime_options.cache_pool=WorkflowCachePoolPreloadForeverShared(max_entries=16)`,用户执行 `run_workflow(...)`,系统 MUST 启用跨 nodes 的 `preload_forever` 共享
  r1,"bounded-preset-supports-pin-for-selected-logical-keys","调用方传入 `WorkflowCachePoolPreloadForeverShared(max_entries=16, pin=(WorkflowCachePoolPin(kind=\"preload_forever\", source_id=\"s1\"),))`",用户执行 `run_workflow(...)`,系统 MUST 将指定的 logical keys 常驻到 workflow_end（避免 refcount 自动释放）
```
