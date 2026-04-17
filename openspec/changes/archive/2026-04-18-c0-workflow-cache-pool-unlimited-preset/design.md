## Context

workflow cache pool 目前通过 runtime policy boundary 的 preset 进行启用（`WorkflowRuntimeOptions.cache_pool`），用于在同一次 workflow 执行内跨 nodes 复用
`preload_forever` 结果并通过 signature 避免错误复用。

现状问题（面向 authoring）：

- 当用户希望“启用 cache pool 但不希望预算限制”时，常见做法是把 `max_entries` 设为一个极大值（语义不清晰、冗余且不可被类型系统约束）。
- bounded preset `WorkflowCachePoolPreloadForeverShared` 存在默认 `max_entries=16`，会在调用方没有明确意图时引入隐式限制，排障时需要额外注意。
- unlimited 场景下，用户还需要理解并手动配置 `pin` 才能避免 refcount 释放带来的“不确定是否仍可复用”的心智负担（需求上希望正交：无限即全局常驻，有限才需要 pin）。

约束：

- 运行时核心必须保持 Python 3.6 兼容（`src/scalim/`）。
- OpenSpec 规范为对外行为 SSOT；实现/测试/文档必须同步并通过门禁（`just openspec-check`、`just check-only-py`、`just test-gate` 等）。

## Goals / Non-Goals

**Goals:**

- 提供显式的 unlimited preset：`WorkflowCachePoolPreloadForeverUnlimited()`，让用户无需通过“大数”表达无限。
- 将 bounded preset 的预算从“隐式默认”调整为“显式必填”，以便用户通过类型约束做出明确选择（unlimited vs bounded）。
- 让 unlimited preset 的生命周期语义默认等价“全部 pin 到 workflow_end”（不做 refcount 释放），避免用户在 unlimited 场景仍需要处理 pin 语义。
- 保持 bounded preset 支持 `pin`，用于“有限 + pin”的正交组合。

**Non-Goals:**

- 不扩展 YAML authoring surface（workflow YAML 仍不支持 cache_pool 配置；仅 runtime entrypoints）。
- 不新增更多 cache_pool knobs（conflict_policy/release_policy/over_budget_policy 仍固定为稳定默认；需要扩展时以新增 preset 方式进行）。
- 不改变 cache pool 的 signature/冲突策略/并发安全语义（这些由现有实现与 `workflow-cache-pool-safety` 规范覆盖）。

## Decisions

1) 新增显式 preset，而不是用 `0` / `None` 表达 unlimited

- 选择：新增 `WorkflowCachePoolPreloadForeverUnlimited()`。
- 理由：
  - `0` 容易被误解为“禁用”；`None` 会引入 Optional 传播与更多分支。
  - 显式 preset 能提供最强的语义可读性与类型约束，用户不会再通过数值含义猜测行为。

2) bounded preset 移除默认 `max_entries=16`，改为必填（BREAKING）

- 选择：`WorkflowCachePoolPreloadForeverShared(max_entries: int, pin: Tuple[...]=())`，`max_entries` 不再有默认值。
- 理由：
  - 用户必须显式选择预算，避免隐式限制。
  - 与 unlimited preset 并列后，调用方通过“选择 preset + 参数形状”即可表达意图（而不是依赖默认值）。

3) unlimited preset 的生命周期语义：release_policy=workflow_end + budget disabled

- 选择：
  - unlimited preset 映射为 `release_policy=workflow_end`（不执行 DAG refcount 自动释放），并禁用 entries 数量预算检查。
  - unlimited preset 不暴露 `pin` 参数（等价“全 pin”）。
- 理由：
  - 该语义满足“无限默认全部常驻”的心智模型；用户无需额外配置 pin。
  - bounded/pin 仍保持正交：只有在“有限预算”时 pin 才有意义。

4) IR/实现表达方式：unlimited 不通过“大数”模拟

- 选择：实现中为 unlimited preset 提供明确分支（例如 `WorkflowCachePoolIr.budget` 允许为空或等价的内部表示），并在 runtime 跳过预算检查。
- 理由：
  - 避免把“无限”降级为“一个很大的有限”，否则会在诊断/事件/未来扩展中产生不一致。

## Risks / Trade-offs

- [BREAKING] `WorkflowCachePoolPreloadForeverShared()` 不再可无参构造 → 需要更新调用方（tests / notebooks / 文档示例）。
  - 缓解：仓库内全量替换为显式 `max_entries=...` 或改用 `WorkflowCachePoolPreloadForeverUnlimited()`；并在文档中给出迁移示例。
- [资源风险] unlimited preset 可能导致 workflow 内存常驻增长。
  - 缓解：默认仍为 `WorkflowCachePoolDisabled()`；unlimited 仅在调用方显式选择时启用；文档强调其适用场景与风险。
- [实现复杂度] IR 需要能够表达“无预算”。
  - 缓解：将变化局限在 workflow cache pool IR 与构造路径（compile/runtime），并通过 tests 覆盖 unlimited/bounded 两条路径。
