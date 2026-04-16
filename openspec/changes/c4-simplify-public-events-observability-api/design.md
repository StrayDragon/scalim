## Context

事件体系与可观测性对外入口当前主要是：

- `scalim.events`：事件 envelope、事件类型常量、与事件目录查询工具
- `scalim.ob.Observability`：observer 注册与 `ObserverManager` 构建门面

现状问题：

- `scalim.events.__all__` 平铺导出大量事件常量与 key 常量，用户需要为简单订阅场景记忆/检索大量符号。
- `Observability` 的策略字段（如 loader_result_policy 等）以多参数 + 字符串组合存在，缺少强类型 options 的集中校验，容易把内部策略语义固化为用户侧依赖。

约束：

- 不能破坏事件热路径语义：事件分发必须保持 wants 短路、payload 构建策略与现有性能边界（`hooks-observability-structure`）。
- `src/scalim/**` 运行时需 Python 3.6 兼容。
- public surface 变更允许 breaking，不做兼容层；全仓一次性升级。

## Goals / Non-Goals

**Goals:**

- 让 `scalim.events` 的 public surface 更结构化、可发现：
  - 在保持 `event_type` 字符串稳定的前提下，把导入体验从“平铺常量”升级为“按主题分组/目录对象”。
  - 提供单一、稳定的入口让用户列举/检索事件类型（例如 catalog API）。
- 让 `scalim.ob` 的 public surface 更可校验：
  - 引入强类型 options（或等价收敛方式），使策略字段集中定义、集中校验、fail-fast。
- 同步治理：public API catalog/docs、import-boundary gate、tests/notebooks 示例一次性升级。

**Non-Goals:**

- 不改变事件 envelope（`Event`）的数据契约与 payload 字段语义。
- 不改变 InstrumentationHub/HookManager 的分发结构与 wants 短路策略。
- 不在本 change 内引入新的观测能力（例如新的可视化格式或新的事件类型）。

## Decisions

### Decision 1: 将事件类型常量的“导入体验”从平铺改为分组对象 + catalog

建议提供一个新的稳定组织方式（示例命名，最终以实现为准）：

- `scalim.events.types`：按主题分组的命名空间对象（例如 `pipeline.*`、`workflow.*`、`loader.*`、`diagnostic.*`）
- `scalim.events.get_event_catalog()`：仍保留作为“可枚举/可检索”的单一入口（已有能力可复用）

并将 `scalim.events.__all__` 收敛到：

- `Event` / `EventDescriptor`
- `get_event_catalog` / `get_event_catalog_map`
- “分组对象”（而不是导出所有单个常量）

理由：

- 满足“可发现、可学习”的目标，同时不改变底层 `event_type` 的稳定性。
- 与 `public-api-surface-governance` 的“减少内部符号泄漏”方向一致：顶层不应无限增长。

备选方案：

- 保持平铺常量不变，仅加文档 → 无法降低符号噪声，也无法形成可 gate 的收敛目标。

### Decision 2: Observability 引入强类型 options（并保持组件装配主线不变）

建议引入：

- `ObservabilityOptions`（或等价 dataclass）：集中承载 `fallback_logger_enabled`、`loader_result_policy`、`loader_result_sample_size` 等策略字段，并在 `__post_init__` 中校验合法性。
- `Observability` 门面改为 `Observability(options=..., observers=[...])` 或提供 `Observability.from_options(...)`，避免构造参数继续膨胀。

同时保持：

- execution/DSL 装配仍以 `components=[Observer/Hook]` 为主线；options 只管理 “manager 构建策略”，不引入额外开关分叉。

### Decision 3: 文档与生成边界

- SSOT：`src/scalim/events/__init__.py` 与 `src/scalim/ob/__init__.py` 的 `__all__`。
- 生成物：
  - public API docs：由 `just gen-docs` 刷新 `.gen.` 页面（不得手改生成物/注入区块）。
  - public surface 审计/跳转：由 `just gen-public-api-jump-imports` 与相关 catalog 生成器写入 `.tmp/`（不提交）。
- 门禁：`just qa` 需要能 fail-fast 指出 exports 漂移与用户材料导入边界问题。

## Risks / Trade-offs

- [风险] Breaking：大量事件常量的导入路径变更 → [缓解] 一次性升级全仓；同时提供 catalog API 让用户按 `event_type` 查找替代路径（不做兼容层）。
- [风险] “分组对象”设计不当会降低可读性 → [缓解] 优先用简单命名空间（模块级常量聚合）而不是复杂 meta-programming；并用 jump-imports 与 docs 示例验证可用性。
- [风险] Observability options 收敛可能改变错误信息/默认值表现 → [缓解] 显式写入 design 的默认值策略，并用测试覆盖默认值与 fail-fast 场景。

## Migration Plan

1. 设计并落地 events 分组对象（保持 `event_type` 值不变），收敛 `scalim.events.__all__`。
2. 引入 `ObservabilityOptions` 并调整 `Observability` 构造方式，补足校验与测试。
3. 全仓升级 imports（docs/skills/notebooks/tests），并更新 public API catalog/docs 生成物。
4. 跑门禁：`just qa`、`just openspec-check`。

## Open Questions

- events 分组的“主题边界”是否需要与现有 `WORKFLOW_EVENT_PREFIX_*` 等常量完全一致，还是以用户理解优先重新组织（实现时需给出明确映射规则）。
