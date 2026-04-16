## Context

本 change 关注 `scalim.dsl.yaml_dsl` 的 **public run API**（`compile/run/run_workflow`）的可用性与可维护性：

- 当前 public surface 围绕一个“超大扁平 `RunOptions` + 若干 workflow 额外参数 + sink/outputs 组合语义”演进，形成多处隐含规则与不一致点。
- `demand` 与 `workflow` 共用一个 options 类型，但两条链路的有效字段/有效组合并不一致（例如 workflow 禁止共享 sink），导致调用侧必须“靠记忆”才能避免踩坑。
- `run_workflow` public facade 仍暴露注入/测试用 knobs（`run_ir_fn` / `compile_demand_yaml_fn`），这会把内部实现结构固化为用户材料的一部分，增加长期演进成本。
- 输出写文件 + 捕获（tee）存在隐式组合语义风险：execution 层为了兼容“写文件 + 传 sink”会自动 tee；这对用户是惊喜行为，对维护者是高回归成本点。

约束与治理：

- `src/scalim/**` 运行时需兼容 Python 3.6（不依赖 `from __future__ import annotations`，typing 需走现有兼容层）。
- 文档治理：`.gen.` 为生成物禁止手改；任何 `BEGIN/END AUTOGEN:<id>` 区块禁止手改区块内部；统一用 `just gen-docs` 刷新。
- 本 change 期望 **不做兼容层**（允许 breaking），以“目标原则优先”为最高指示。

下游集成现状（已确认）：

- 目前外部需要适配的唯一“真实用户使用点”在下游集成系统 `INTEGRATION_APP`（目录 `INTEGRATION_DIR`），主要调用 `run_workflow(...)` 并关注默认值语义是否保留。

## Goals / Non-Goals

**Goals:**

- Public run API 以“每个入口只有一个 `options` 对象”驱动，且 `workflow` 入口也满足该约束（不再通过额外 kwargs 拼装运行策略）。
- 将运行期契约拆分为两个明确类型：
  - `DemandRunOptions`：独立 demand 的公开运行契约（同时作为 workflow 节点默认 demand options 的承载）
  - `WorkflowRunOptions`：workflow 的公开运行契约（内部显式包含 `demand: DemandRunOptions`）
- **移除 `sink` 作为 public DSL 运行期契约**：改为少量内置、可校验的 capture 策略（例如 `CaptureRows`），从根上消灭“隐式 tee”语义组合与 sink 兼容性陷阱。
- per-run patch 模型对齐新的 options 结构：patch 明确作用于 “节点的 demand options”，并定义可 patch 边界（禁止覆盖安全边界）。
- Public workflow facade 移除注入/测试专用 knobs；保留 internal/test-only 注入入口供 tests 使用。
- 同步更新 docs / notebooks / tests / public-api-exports catalog，使门禁可验证、漂移可发现。

**Non-Goals:**

- 不提供旧 API 的向后兼容或 deprecation 迁移层（本 change 允许 breaking）。
- 不在本 change 内把 options 体系迁移到 Pydantic（保持 dataclasses 为主，后续可演进）。
- 不改变 YAML DSL 语义本身（除非为了修复“隐式 tee/输出捕获不一致”所必须的行为边界调整）。
- 不新增大规模新能力（例如“选择性运行 workflow 子集”），仅重构 public run surface 与契约结构。

## Decisions

### Decision 1: 采用 “Scheme 3 + Scheme 2” 作为主路径

结论：以 **Scheme 3（Demand/Workflow 分型）** 为主，叠加 **Scheme 2（sink 从 public surface 下沉 + 内置 capture）**。

理由：

- “同一个 RunOptions 同时服务 demand/workflow”是当前心智负担与不一致的根源；分型能从类型层面消灭“哪些字段对 workflow 无效”的记忆成本。
- `sink` 作为用户可随意注入的执行层抽象，会迫使 DSL 层承诺大量兼容/组合语义；将其移出 public surface，能把输出/捕获/tee 语义收敛为少量可校验策略，从根上解决隐式规则与维护成本。

备选方案回顾：

- Scheme 1（仍保留单 RunOptions 但内部强分组）可缓解扁平化问题，但仍保留“同一类型跨入口不一致”的根源，且仍难彻底收敛 sink/tee 语义。

### Decision 2: workflow 入口也只接受 `options`

目标是把 `run_workflow` 从 “options + 多个 kwargs” 变为 “options-only”，并把：

- `run_options_patches_by_run_id`
- `workflow_runtime_options`
- `path_aliases`

全部迁入 `WorkflowRunOptions`，以满足“单 options 对象驱动入口”的一致原则。

### Decision 3: 移除 public `sink`，以 CapturePolicy 显式表达捕获语义

Public DSL run API 不再接受/暴露 `sink`（包括 options 字段与 entrypoint 参数），改用内置 capture 策略表达：

- `CaptureNone`（默认）：不捕获内存数据
- `CaptureRows`：显式捕获行数据（对外返回 `scalim.sinks.rows.InMemoryRows`；内部实现通过 execution 的 `capture_in_memory_rows` + `InMemoryRowsSink` 装配）

核心语义：

- “写文件”与“捕获”是两个正交选择；组合时的 tee 必须由 capture 明确表达，而不是“多传一个参数”触发隐式推导。
- demand 与 workflow 节点的捕获规则边界一致（workflow 只是在节点粒度执行 demand）。

### Decision 4: workflow patch 只作用于 “节点 demand options”，且有明确 policy 边界

per-run patch 的语义调整为：

- patch 的对象是 `WorkflowRunOptions.demand`（节点默认 demand options）
- patch 只允许覆盖被声明为 patchable 的字段集合
- patch 禁止覆盖安全边界（allowlist/trusted mode 等）
- 合并阶段 fail-fast 校验，并在错误信息中指向 run_id + 字段路径

### Decision 5: 注入/测试 knobs 迁入 internal/test-only

公开入口 `scalim.dsl.yaml_dsl.run_workflow` 不再暴露：

- `run_ir_fn`
- `compile_demand_yaml_fn`

tests 若需要注入点，改为使用 internal/test-only 入口（例如 `scalim.dsl.yaml_dsl._internal.*` 或 tests helper），避免 public surface 固化内部结构。

### Decision 6: 文档/生成物边界与漂移门禁（drift gate）

本 change 涉及大量 public surface 变更，必须明确以下边界：

- SSOT：public API 的符号级 SSOT 仍是各模块的 `__all__`（不引入手工维护的硬 manifest）。
- 本 change 使用 `openspec/changes/c1-simplify-public-run-api/gen-public-api-exports.py` 生成审计快照 `public-api-exports.md`，用于 review 与门禁对齐（快照不是 SSOT）。
- 仓库级 public API 治理工具链见 `c0-public-api-governance-tooling`：`just gen-public-api-exports-catalog`/`just check-public-api-curated-entrypoints`（产物写入 `.tmp/`，不提交）。
- docs 站点的生成物与 injected-block 必须通过 `just gen-docs` 刷新；禁止手工编辑 `.gen.` 文件与注入区块内容。
- 验收以门禁命令为准：`just qa`（lint/tests + drift checks）与 `just openspec-check`（sanitize + validate）。

### Decision 7: capture 扩展形态先收敛为最小集合（不引入 DataFrame capture / output_id capture）

本 change 的 capture 先以“可落地 + 可验证”为优先，收敛为：

- 仅 `CaptureNone` / `CaptureRows` 两种策略
- `CaptureRows` 的捕获结果对外只承诺 `InMemoryRows`（不承诺 pandas DataFrame；DataFrame 仅作为 `to_dataframe()` 的可选便捷转换）
- 不在本 change 内引入 “捕获指定 output_id” 或 “按 output_id 捕获多份工件” 的新能力（未来若需要，走独立 change 设计与测试矩阵）

边界说明：

- capture 是显式 opt-in；默认 `CaptureNone`
- 若输出端为列式 sink（例如非流式输出导致的 `IColumnSink`），capture 目前允许 fail-fast，并在错误信息中指引开启流式输出或关闭 capture（语义清晰优先于隐式兜底）

### Decision 8: 结果对象更名为 `DemandRunResult`（不保留 `RunResult` 兼容别名）

为与 `DemandRunOptions` 对齐并消除歧义，本 change 将 demand 的运行结果类型定名为：

- `DemandRunResult`

并明确：

- 不保留旧名 `RunResult` 的兼容 alias（允许 breaking；一次性升级 tests/notebooks/docs/下游集成）
- `DemandRunResult` 直接承载捕获结果（例如 `captured_rows: Optional[InMemoryRows]`），不再暴露 `sink`

### Decision 9: 注入入口放置在 `scalim.dsl.yaml_dsl._internal`，且不进入 public exports

为彻底移除注入/测试 knobs 对公共 surface 的固化，本 change 的约束升级为：

- `scalim.dsl.yaml_dsl.run_workflow`（curated public facade）不暴露注入参数
- `scalim.dsl.yaml_dsl.workflow_entrypoints.run_workflow`（稳定入口）同样不暴露注入参数
- tests 若需要注入，使用 internal/test-only 入口，例如：
  - `scalim.dsl.yaml_dsl._internal.workflow_injected_entrypoints.run_workflow_injected(...)`

internal 入口要求：

- 所在模块必须显式 `__all__ = ()`（避免进入 `public-api-exports` catalog）
- 函数名显式表达“注入/测试用途”，避免被误当成稳定对外 API

## API Deltas (Before / After)

本节将独立变动点逐条列出（实现与任务拆分也将以此为分解单位）。

### Change Point C1: `RunOptions` → `DemandRunOptions` + `WorkflowRunOptions`

**Before**

- `scalim.dsl.yaml_dsl.RunOptions`：单一 options 类型同时服务 `demand` 与 `workflow`

**After**

- `scalim.dsl.yaml_dsl.DemandRunOptions`：仅用于 `compile/run`
- `scalim.dsl.yaml_dsl.WorkflowRunOptions`：仅用于 `run_workflow`，并显式包含 `demand: DemandRunOptions`

**Impact**

- 所有 public 示例、tests、notebooks 必须更新导入路径与构造方式。

### Change Point C2: `run_workflow` 变为 options-only

**Before**

`run_workflow(workflow_yaml_path, *, options, run_options_patches_by_run_id=..., workflow_runtime_options=..., path_aliases=..., ...)`

**After**

`run_workflow(workflow_yaml_path, *, options: WorkflowRunOptions)`

其中 `patches/runtime/path_aliases` 都在 `WorkflowRunOptions` 内。

### Change Point C3: per-run patch 类型与边界更新

**Before**

- `WorkflowRunOptionsPatch`：与旧 `RunOptions` 强耦合，patch 边界与 policy 不够显式

**After**

- `WorkflowNodePatch`（名称可调整，但语义需明确）：只 patch 节点的 demand options 子集；禁止覆盖安全边界；fail-fast 校验

### Change Point C4: 移除 public `sink`，用 capture 策略替代

**Before**

- demand：`options.sink` 可能与文件输出组合触发隐式 tee（execution 层自动 tee）
- workflow：禁止共享 sink，但依然与同一个 `RunOptions` 类型耦合，导致“字段存在但不可用”

**After**

- public DSL options 中不再出现 `sink`
- `DemandRunOptions.capture`（或等价字段）显式表达捕获需求
- 语义对齐：demand 与 workflow 节点一致

### Change Point C5: demand 运行结果结构更新（不再暴露 sink）

**Before**

- `RunResult` 带 `sink`（并提供 `to_dataframe()` 依赖 `sink.get_data()`）

**After**

- `DemandRunResult` 直接承载捕获结果（例如 `captured_rows`）
- `to_dataframe()` 仅在捕获开启时可用（否则 fail-fast 指引开启 capture）

### Change Point C6: components 语义拆分（workflow-level vs demand-level）

**Before**

- workflow 与 demand components 混用，存在“哪些事件属于 workflow 编排层、哪些属于 demand 执行层”的语义缠结

**After**

- `WorkflowRunOptions.workflow_components`：workflow 编排层 instrumentation
- `DemandRunOptions.components`（或 `demand_components`）：每个 demand 执行层组件

### Change Point C7: 注入/测试 knobs 从 public facade 移除

**Before**

- public `run_workflow` 暴露 `run_ir_fn/compile_demand_yaml_fn`

**After**

- public `run_workflow`（curated facade + stable workflow entrypoint）都不再暴露
- internal/test-only 入口承载注入点（tests 迁移），并显式放在 `scalim.dsl.yaml_dsl._internal.*`

### Change Point C8: 文档、notebooks、治理材料同步

涉及同步点（SSOT 与生成入口）：

- `public-api-exports.md`：由 `gen-public-api-exports.py` 生成（SSOT 为源码 `__all__`）
- docs 站点：任何 `.gen.` 与 injected-block 由 `just gen-docs` 生成/注入
- OpenSpec：提交前 `just openspec-check`

### Change Point C9: 下游 `INTEGRATION_APP` 适配与默认值核对

下游当前只调用 `run_workflow` + 传 `allowed_modules/init_vars/template_vars/batch_size/components` + patch `DemandDiagnosticsOverride`。

适配重点：

- 新的 `WorkflowRunOptions` 构造方式
- `DemandDiagnosticsOverride` patch 路径是否保持等价能力
- 默认值语义（例如 batch_size 的默认/覆盖规则）不发生意外漂移

## Risks / Trade-offs

- **大规模 breaking** → 通过一次性升级 tests/notebooks/docs + 下游集成来吸收；不做兼容层。
- **移除 sink 降低扩展性** → 通过 internal/execution API（或 internal/test-only 入口）保留高级用户能力；public surface 仅承诺稳定 capture。
- **捕获 rows 可能带来内存风险** → capture 必须 opt-in；在设计上预留未来扩展（例如限制行数、仅捕获某些 outputs）。
- **components 拆分可能改变观测行为** → 明确语义边界，补足回归测试覆盖（workflow instrumentation vs demand instrumentation）。
- **workflow options-only 可能导致调用方改动较大** → 通过清晰的 before/after delta 与任务拆解降低迁移风险。

## Migration Plan

实施建议以“可验证、可回滚”为导向（尽管本 change 不提供兼容层，回滚仍可通过 revert 处理）：

1. 引入新 options/capture/patch 类型（contracts 层），并建立 fail-fast 校验与错误信息规范。
2. 重构 demand 入口（`compile/run`）仅接受 `DemandRunOptions`，实现 capture 策略并移除 public sink。
3. 重构 workflow 入口为 options-only，拆分 workflow/demand components；把注入点迁入 internal/test-only。
4. 全量更新 tests/notebooks/docs 与 public API exports catalog（用门禁命令验证漂移闭环）。
5. 适配下游 `INTEGRATION_APP`（目录 `INTEGRATION_DIR`）并核对默认值语义。
6. 运行验收：
   - `python openspec/changes/c1-simplify-public-run-api/gen-public-api-exports.py`
   - `just gen-docs`（如涉及 docs 注入/生成物）
   - `just qa`
   - `just openspec-check`

## Future Extensions (Out of scope)

以下能力不在本 change 落地范围内；若后续确有需求，建议独立 change 专项设计 + 测试矩阵：

- capture 增强：`CaptureRows(max_rows=..., max_cells=..., max_bytes=...)` 等显式内存护栏
- capture 输出选择：支持 “捕获指定 output_id” 或 “按 output_id 捕获多份工件”（需要与 output_composition/managed artifacts 语义对齐）
- capture 格式扩展：例如 `CaptureCsv` / `CaptureParquet` 等（避免把 pandas/pyarrow 等依赖引入 runtime 基线）
