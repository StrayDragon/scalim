## Context

当前 workflow 执行链路位于 `scalim.dsl.by_yaml.runtime.*` 下，包含了并发调度、失败策略、ctx/artifacts、资源管理(workbook/csv/sheetbook)、事件桥接与可观测性装配等完整“执行编排”职责。这与仓库的分层边界(DSL runtime 作为纯 adapter/编译器，execution 侧提供统一 IR 编排入口)不一致，且难以通过 QA 做硬门禁守护依赖方向与 SSOT。

约束：

- `src/scalim/` 运行时必须兼容 Python 3.6（避免 3.8+ stdlib 能力；避免 `from __future__ import annotations`）。
- `src/scalim/` 内扩展 typing 仅允许通过 `vendor/compact/typing_extensionsx.py`。
- 文档治理：任何 `.gen.*` 文件与 `AUTOGEN` 注入区块禁止手改；OpenSpec 与 docs 变更需通过 `just openspec-check`/`just qa` 门禁。
- 假设更高优先级 change 会先合并：例如 `vendor-sync-legacy-vendors-libs` 提供的 vendors 同步入口与发布约定。

## Goals / Non-Goals

**Goals:**

- 将 workflow 的执行编排与运行时能力下沉到 framework 层：新增 `scalim.workflow.*` 作为 workflow runtime SSOT。
- 保持 YAML workflow 的官方入口在 `scalim.dsl.by_yaml`：新增 `scalim.dsl.by_yaml.workflow_entrypoints.run_workflow(...)`，负责 workflow YAML 的加载/校验/编译与依赖注入。
- 明确依赖方向：`scalim.workflow/**` 不得反向依赖 `scalim.dsl/**`；通过 pytest gate 硬约束并避免回归。
- 迁移/拆分过程中保持行为等价：结果顺序、失败策略、事件归因、资源写入/清理语义不变（仅路径与模块边界调整）。
- 一次性升级仓库内所有旧路径引用（tests/fixtures/YAML loader/allowlist），不提供旧路径兼容 shim。

**Non-Goals:**

- 不引入新的 workflow 语法或运行特性（本轮是架构分层与 SSOT 收敛）。
- 不新增新的顶层公共 facade（仍按显式模块路径导入；`__init__.py` 保持最小 glue）。
- 不在本轮引入新的可选依赖或改变已有 optional dependency 策略。

## Decisions

1) **新增 `scalim.workflow` 作为 workflow runtime SSOT（framework 层）**

- 新增包 `src/scalim/workflow/`，内部按职责拆分：execute/scheduler、ctx/artifacts、resources、loaders、report 等。
- `__init__.py` 仅提供最小稳定入口（必要的 `__all__` 白名单），内部实现不通过包级 re-export 暴露。
- workflow runtime 允许依赖 `spec.ir.workflow`、`execution.run_ir`、`execution.workflow_cache_pool`、`hooks/ob/events/sinks/utils`，但 **禁止** 依赖 `dsl`。

2) **YAML workflow 入口固定为 `scalim.dsl.by_yaml.workflow_entrypoints.run_workflow`**

- `workflow_entrypoints` 负责：
  - load workflow YAML → `WorkflowConfig`
  - compile workflow config → `WorkflowIr`
  - 以显式 callback 注入的方式调用 `scalim.workflow` 的统一执行入口
- 入口需要支持每次调用级别的显式注入（例如 `run_ir_fn` / `compile_demand_fn`），且不依赖模块全局变量，以避免并发串扰（与 `workflow-runtime-quality-and-test-stability` 对齐）。

3) **依赖反转：framework 只接收 `WorkflowIr` + callbacks，不接触 YAML config types**

- `scalim.workflow` 的执行入口以 `WorkflowIr` 为输入；当 demand 节点就绪时，通过注入的 `compile_demand_fn(...)` 获取：
  - `DemandIr`
  - `ExecutionRequest`
  - 以及 workflow runtime 需要的少量 DSL 派生信息（纯数据契约）,避免 framework 直接 introspect `DemandConfig`：
    - `scalim.spec.ir.workflow.WorkflowDemandNodeDerivedIr`
      - `workbook_output_paths_abs`（用于 workflow 侧做路径冲突预检）
      - `workflow_managed_csv_output_ids`（用于 workflow-managed outputs 的授权/托管边界）

4) **将 runtime/workflow 模块从 by_yaml runtime 移除**

- 删除 `src/scalim/dsl/by_yaml/runtime/workflow_*.py`（execute/compile/load/loaders/resources/report/entrypoints）。
- 将 workflow “加载与编译”相关模块迁移到 `src/scalim/dsl/by_yaml/`（不属于 runtime adapter），仅保留 demand runtime 的 adapter/编译器职责在 `dsl/by_yaml/runtime/` 内。

5) **QA gate：以 pytest AST 扫描守住依赖方向**

- 新增测试用例扫描 `src/scalim/workflow/**/*.py`，禁止 `import scalim.dsl...` 或 `from ...dsl... import ...`。
- 追加扫描 `src/scalim/dsl/by_yaml/runtime/**/*.py`，禁止出现 workflow runtime 模块回流（例如 `workflow_*.py` 或对 `scalim.workflow` 的执行编排依赖）。

## Risks / Trade-offs

- [破坏性路径升级] workflow 入口与内置 loader 的 module path 变化会导致调用方导入失败 → 仓库内一次性升级所有引用，并在 specs/docs 中写死新路径与迁移点。
- [重构回归风险] workflow 涉及并发与清理逻辑，拆分后容易引入行为漂移 → 以既有 workflow pytest 套件作为行为护栏，新增依赖方向 gate；优先移动/重命名保持逻辑不变，再做微调。
- [依赖倒灌] framework 若直接 import DSL 会在未来演进中造成循环依赖 → 用 gate 强制单向依赖，并以 callback 注入取代静态导入。
