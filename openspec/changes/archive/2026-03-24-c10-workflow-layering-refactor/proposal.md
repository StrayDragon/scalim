## Why

当前架构的核心分层设想是：

- DSL(YAML/Python) → IR(pure data) → Framework(planning/execution/orchestration/observability) → Sink(I/O)

但 workflow 的实现已经明显越过了这条边界：在 `scalim.dsl.by_yaml.runtime.*` 内部存在完整的 workflow 执行编排(并发调度、失败策略、资源与 ctx 管理、workflow 级事件与归因注入、ObserverManager 生命周期等)。这使得：

- DSL runtime 失去“纯 adapter/编译器”的定位(与 `dsl-runtime-structure` 的边界不一致)
- 规则与实现容易漂移(同类校验/路径预检/事件桥接在多处复制)
- 分层依赖方向难以通过 QA 链路做强约束，导致回归风险高

因此需要一次强重构：将 workflow runtime 从 YAML DSL runtime 下沉到 framework 层，并用自动化门禁守住依赖方向与 SSOT 一致性。

## What Changes

- 新增 `scalim.workflow.*` 作为 workflow 的 framework/runtime SSOT：承载 workflow 的调度执行、资源/ctx/artifacts 管理、workflow-level events、内置 workflow loaders 等。
- 将 workflow YAML 的角色收敛为“前端编译 + 注入点”：保留 `scalim.dsl.by_yaml.workflow_entrypoints.run_workflow(...)` 作为官方入口，负责加载/校验/编译 workflow YAML 为 `WorkflowIr`，并注入 demand 编译回调与执行回调给 framework。
- **BREAKING** 移除 `scalim.dsl.by_yaml.runtime/workflow_*.py` 这批 workflow runtime 模块；workflow 不再属于 demand 的 runtime adapter。
- **BREAKING** 内置 workflow loader 的官方路径升级为 `scalim.workflow.loaders:...`(例如 `sheetbook_sheet_rows`)；测试/fixtures/YAML 示例将一次性升级，不做兼容 shim。
- 增加 QA gate：以 AST 扫描/导入冒烟测试的形式，硬性约束 `scalim.workflow/**` 不得反向依赖 `scalim.dsl/**`，并避免 workflow 逻辑回流到 DSL runtime。

## Capabilities

### New Capabilities
<!-- 无 -->

### Modified Capabilities
- `yaml-dsl-workflow`: workflow 官方入口从 `scalim.dsl.by_yaml.runtime.workflow_entrypoints` 调整为 `scalim.dsl.by_yaml.workflow_entrypoints`；workflow 执行编排下沉到 framework。
- `workflow-sheetbook-resources`: 内置 sheetbook loader 引用路径升级为 `scalim.workflow.loaders:*`（替换旧的 runtime 路径）。
- `dsl-runtime-structure`: 明确 by_yaml runtime 仅承担 demand 的 adapter/编译器职责，workflow runtime 不属于该层。
- `workflow-runtime-module-organization`: workflow runtime 迁移到 `scalim.workflow.*`，并保持职责子模块化与稳定入口策略。
- `workflow-runtime-quality-and-test-stability`: workflow 入口需支持 per-call 显式依赖注入(run_ir/compile callbacks)且不依赖模块全局变量；JSON-like 校验等规则保持单一 SSOT 并在 workflow ctx 等路径复用。
- `module-organization`: 扩展“核心层级依赖方向必须保持单向”的要求，增加 `workflow`(framework) 不得依赖 `dsl` 的可审计约束，并由 QA 门禁守护。
- `testing-quality`: py36/typing-extensions 隔离环境的 workflow import smoke test 调整为覆盖新的 workflow 稳定入口模块。

## Impact

- 受影响代码/入口：
  - 新增：`src/scalim/workflow/**`
  - 新增/调整：`src/scalim/dsl/by_yaml/workflow_entrypoints.py`
  - 删除：`src/scalim/dsl/by_yaml/runtime/workflow_*.py`
  - 测试与 fixtures：更新 workflow YAML 中的 loader 引用与 allowlist 模块集合
- 文档与规范 SSOT：
  - OpenSpec 规范 SSOT 为 `openspec/specs/**/spec.md`；变更后将同步更新相关 specs 并通过 `just openspec-check` 校验。
  - 架构说明 SSOT 更新 `ARCH.md` 并保持与 `docs/doc/architecture/arch.md` 一致；由 `just doc-governance-check`/`just qa` 漂移门禁兜底。
- 与更高优先级变更的关系：
  - 假设 `vendor-sync-legacy-vendors-libs` 会先合并：本变更中新增/迁移的核心运行时代码遵循其 vendors 同步/发布约定。
