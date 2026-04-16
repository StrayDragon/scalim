## 1. Events Public Facade: Structured Event Types

- [x] 1.1 引入 `EventType`（推荐 `class EventType(str, Enum)`）：其 `.value` 必须与既有 `EVENT_*` 字符串完全一致；必要时实现 `__str__ -> self.value` 以降低误用（验收：事件热路径语义不变；字符串值域稳定）。
- [x] 1.2 引入 workflow 常量 enum：`WorkflowNodeEndStatus` 与 `WorkflowNodeCancelledReason`（值保持不变），并从 facade 导出（验收：调用方不再需要导入平铺常量集合即可表达有限取值）。
- [x] 1.3 提供（可选）分组视图 `scalim.events.type_groups`（workflow/node/cache/resource + 其它按 `event_type` 前缀分组），仅提升可发现性，不引入新值（验收：分组确定性、可维护；不依赖 typed payload 导入路径）。

## 2. Shrink `scalim.events.__all__` (Breaking)

- [x] 2.1 收敛 `src/scalim/events/__init__.py` 的 `__all__`：保留 `Event`/`EventDescriptor`/`EventType`/catalog API 等少量稳定入口，移除平铺 `EVENT_*` 与 prefix 常量（验收：public API docs/export 审计视图能体现收敛；用户材料迁移完成）。
- [x] 2.2 更新 repo 内部与用户材料的使用方式：从 `EVENT_*` 导入迁移为 `EventType`（或 `type_groups` 分组视图）并保持行为一致（验收：核心订阅/过滤逻辑仍以 `event_type` 字符串工作；`get_event_catalog` 仍可枚举/检索事件目录）。

## 3. Observability Public Facade: Typed Options + Fail-fast

- [x] 3.1 新增 `ObservabilityOptions`（或等价 dataclass）集中承载策略字段并在 `__post_init__` 校验合法性；调整 `Observability` 构造方式为 options-only（验收：非法组合 fail-fast 且错误包含字段路径；组件装配主线 `components=[Observer/Hook]` 不变）。
- [x] 3.2 更新 `src/scalim/ob/__init__.py` 的导出面（验收：`from scalim.ob import Observability, ObservabilityOptions` 可用；docs/示例迁移完成）。

## 4. Migrate Docs / Notebooks / Tests

- [x] 4.1 迁移用户材料：用 `EventType`/`ObservabilityOptions` 替换旧导入路径与 “magic strings” 用法（验收：`docs/doc/**`、`notebooks/marimo/**`、`agentdev/skills/**` 不再出现 `from scalim.events import EVENT_...`）。
- [x] 4.2 增补/更新测试覆盖：断言 `EventType` 值与旧字符串一致、catalog 可用、Observability options 校验生效（验收：新增测试能捕获回归；示例 public API suite 全绿）。

## 5. Public API Catalog / Generated Docs

- [x] 5.1 刷新 public API 文档与生成物（验收：不手改任何 `*.gen.*` 与 injected blocks；运行 `just gen-docs` 后无 drift，且 Tier1 表格/exports 反映 events/ob 收敛后的导出面）。
  - SSOT：`src/scalim/events/**`、`src/scalim/ob/**` 的字面量 `__all__` + Tier1 markers
  - 生成入口：`just gen-docs`

## 6. QA / Drift Gates

- [x] 6.1 OpenSpec 校验（验收：`just openspec-check` 通过；包含 sanitize + validate）。
- [x] 6.2 Repo 质量门禁（验收：`just qa` 通过，包含 lint/tests + drift checks）。
