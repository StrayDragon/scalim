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

### Decision 1: 事件类型常量收敛为 Enum + 确定性分组视图（保持 `event_type` 字符串稳定）

对外新增一个**唯一的事件类型入口**：

- `scalim.events.EventType`：推荐实现为 `enum.Enum`（可用 `class EventType(str, Enum)`），其 `.value` 必须与现有 `EVENT_*` 字符串完全一致，确保 `Event.event_type` 的稳定性不变。
-（可选）`scalim.events.type_groups`：一个“分组视图”（namespace 对象），仅用于提升可发现性；内部引用 `EventType`，不引入任何新值。（说明：由于 stdlib 同名模块冲突门禁，避免使用 `scalim.events.types` 作为模块名）

分组边界（推荐：确定性 + 可维护）：

- **workflow 子分组**：按现有 `WORKFLOW_EVENT_PREFIX_*` 的三类边界组织为 `workflow.node` / `workflow.cache` / `workflow.resource`。
- **其余事件**：按 `event_type` 字符串的第一个 token（`event_type.split("_", 1)[0]`）确定一级分组，例如：
  - `pipeline_start` / `pipeline_end` → `pipeline`
  - `batch_start` / `batch_end` → `batch`
  - `loader_call` / `loader_retry` / `loader_slim` → `loader`
  - `diagnostic_warning` → `diagnostic`

注意：

- 分组只改变“导入体验/可发现性”，不改变底层分发逻辑与 `Event.event_type` 的值域。
- 为避免 `Enum` 的 `str(x)` 默认输出为 `EventType.X` 导致误用，建议实现 `EventType.__str__ -> self.value`（或在代码/示例中强制使用 `.value`）。

并将 `scalim.events.__all__` 收敛到：

- `Event` / `EventDescriptor`
- `EventType`（以及可选的 `types` 分组视图）
- `get_event_catalog` / `get_event_catalog_map`
-（视需要保留）workflow attribution meta keys（数量少且语义明确）

备选方案：

- 保持平铺 `EVENT_*` 常量不变，仅加文档 → 无法降低符号噪声，也无法形成可 gate 的收敛目标。

### Decision 2: workflow status/reason 等有限取值常量同样 enum 化

将以下集合从“可随意被改写的字符串常量”升级为 enum（值保持不变）：

- `WORKFLOW_NODE_END_STATUS_{OK,ERROR}` → `WorkflowNodeEndStatus`
- `WORKFLOW_NODE_CANCELLED_REASON_*` → `WorkflowNodeCancelledReason`

### Decision 3: Observability 引入强类型 options（并保持组件装配主线不变）

建议引入：

- `ObservabilityOptions`（或等价 dataclass）：集中承载 `fallback_logger_enabled`、`loader_result_policy`、`loader_result_sample_size` 等策略字段，并在 `__post_init__` 中校验合法性。
- `Observability` 门面改为 `Observability(options=..., observers=[...])` 或提供 `Observability.from_options(...)`，避免构造参数继续膨胀。

同时保持：

- execution/DSL 装配仍以 `components=[Observer/Hook]` 为主线；options 只管理 “manager 构建策略”，不引入额外开关分叉。

### Decision 4: 文档与生成边界

- SSOT：`src/scalim/events/__init__.py` 与 `src/scalim/ob/__init__.py` 的 `__all__`。
- 生成物：
  - public API docs：由 `just gen-docs` 刷新 `.gen.` 页面（不得手改生成物/注入区块）。
  - public surface 审计/跳转：由 `just gen-public-api-jump-imports` 与相关 catalog 生成器写入 `.tmp/`（不提交）。
- 门禁：`just qa` 需要能 fail-fast 指出 exports 漂移与用户材料导入边界问题。

## Public Surface Diffs

以 “Tier1 curated entrypoint = `scalim.events` / `scalim.ob`” 为基准，预期对外变化为：

- **新增（Tier1）**：
  - `scalim.events.EventType`
  - `scalim.events.WorkflowNodeEndStatus`
  - `scalim.events.WorkflowNodeCancelledReason`
  -（可选）`scalim.events.type_groups`（分组视图）
  - `scalim.ob.ObservabilityOptions`（或等价 options dataclass）
- **移除 / 收敛（从 `scalim.events` 顶层）**：
  - 平铺 `EVENT_*` 常量从 `scalim.events.__all__` 移除
  - `WORKFLOW_EVENT_PREFIX_*` / `WORKFLOW_EVENT_PREFIXES` 从 `scalim.events.__all__` 移除（若仍需要，仅作为内部实现常量保留）
- **更新**：
  - docs/示例：从 `from scalim.events import EVENT_PIPELINE_START` 迁移为 `from scalim.events import EventType`（以及可选的 `types` 视图）

## Risks / Trade-offs

- [风险] Breaking：大量事件常量的导入路径变更 → [缓解] 一次性升级全仓；同时提供 catalog API 让用户按 `event_type` 查找替代路径（不做兼容层）。
- [风险] “分组对象”设计不当会降低可读性 → [缓解] 优先用简单命名空间（模块级常量聚合）而不是复杂 meta-programming；并用 jump-imports 与 docs 示例验证可用性。
- [风险] Observability options 收敛可能改变错误信息/默认值表现 → [缓解] 显式写入 design 的默认值策略，并用测试覆盖默认值与 fail-fast 场景。

## Migration Plan

1. 引入 `EventType` + workflow enums，并提供（可选）`types` 分组视图；保持所有 `.value` 与现有 `event_type` 字符串一致，同时收敛 `scalim.events.__all__`（移除平铺常量）。
2. 引入 `ObservabilityOptions` 并调整 `Observability` 构造方式，补足校验与测试。
3. 全仓升级 imports（docs/skills/notebooks/tests），并更新 public API catalog/docs 生成物。
4. 跑门禁：`just qa`、`just openspec-check`。
