# language: zh-CN
# capability: workflow-cache-pool
# purpose: 提供 workflow-scope 的缓存池(`cache_pool`),用于在同一次 workflow 执行内跨 nodes 复用可共享缓存条目(当前主要用于 `preload_forever` 结果),并通过 signature-based keys/冲突策略/生命周期(refcount+pin)/预算策略/观测事件/并发安全确保"复用正确且可诊断". [rev:c25]
# scope: src/scalim/
功能: workflow-cache-pool

  @req:r86 @human
  场景: workflow options expose a stable `cache_pool` configuration (replacing `share_preload_cache`)
    - 系统 MUST 将 workflow cache pool 的配置入口收敛到 runtime policy boundary，并保持对外配置面受限（preset-based）：
      - workflow YAML MUST NOT 再接受 `workflow.options.cache_pool`；旧的 `workflow.options.share_preload_cache` MUST 被拒绝。出现时 MUST fail-fast 并给出迁移指引。
      - 封闭 preset 集合与其可见 knobs / 固定语义：

      | preset | 可见 knobs | 固定语义 |
      | --- | --- | --- |
      | `WorkflowCachePoolDisabled()`（默认） | 无 | 不共享 preload_forever |
      | `WorkflowCachePoolPreloadForeverUnlimited()` | 无（不暴露 budget/pin） | `release_policy=workflow_end`（不启用 DAG refcount 自动释放）；禁用 entries 数量预算检查 |
      | `WorkflowCachePoolPreloadForeverShared(max_entries, pin=...)` | `max_entries`（MUST 为正整数且 MUST 显式提供，无隐式默认）；`pin`（MAY，把指定 logical keys 常驻到 workflow_end） | `release_policy=dag_refcount`；`budget.over_budget_policy=fail_fast` |

      - 其余策略 MUST 固定为稳定默认且不对外暴露 knobs（例如 `conflict_policy=error`）。
    假如 workflow YAML 包含 `workflow.options.cache_pool`
    当 用户执行 validate/compile 或运行入口解析
    那么 系统 MUST fail-fast
    假如 调用方传入 `workflow_runtime_options.cache_pool=WorkflowCachePoolPreloadForeverUnlimited()`
    当 用户执行 `run_workflow(...)`
    那么 系统 MUST 启用跨 nodes 的 `preload_forever` 共享
    假如 调用方传入 `workflow_runtime_options.cache_pool=WorkflowCachePoolPreloadForeverShared(max_entries=16)`
    当 用户执行 `run_workflow(...)`
    那么 系统 MUST 启用跨 nodes 的 `preload_forever` 共享
    假如 调用方传入 `WorkflowCachePoolPreloadForeverShared(max_entries=16, pin=(WorkflowCachePoolPin(kind="preload_forever", source_id="s1"),))`
    当 用户执行 `run_workflow(...)`
    那么 系统 MUST 将指定的 logical keys 常驻到 workflow_end（避免 refcount 自动释放）
