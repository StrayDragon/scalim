## Context

本变更为纯文档变更：将 `workflow` 的 `stage_barrier` 调度与 `stage` 归因相关的残留风险收敛为一份可长期查阅的 checklist（risk register），避免风险分散在讨论记录、commit message 或临时 notebook 里。

当前实现已落地，并有 spec / 测试覆盖核心路径，但仍存在“语义 + 可观测性 + 性能印象”强耦合的后续验收风险：

- 默认调度 preset 为 `pipeline`，`stage_barrier` 需要显式 opt-in（typed runtime options）
  - 代码：`src/scalim/dsl/yaml_dsl/workflow_types.py`、`src/scalim/dsl/yaml_dsl/workflow_compile.py`
  - 测试：`tests/yaml_dsl/test_yaml_dsl_workflow.py`
- `stage_barrier` 的严格阶段屏障由 controller 在 ready-queue 调度处强制（仅调度当前 stage 的节点，直到该 stage 全部终态后才推进）
  - 代码：`src/scalim/workflow/execute_controller.py`
- 对外的 `stage` 归因使用用户心智模型：demand 节点的 `stage=topology level`；内部 write nodes 折叠到其输入 demand 的 `stage`
  - 代码：`src/scalim/workflow/stage_attribution.py`
  - viz snapshot：`src/scalim/ob/presets/viz/workflow.py`（节点 `data.level` 使用折叠后的 stage）
  - 测试：`tests/workflow/test_workflow_viz_workflow.py`
- 可观测性边界：
  - workflow node 事件 payload 已包含 `schedule_mode` 与 `stage`（便于强消费方解析）
  - viz replay 的事件流保持 payload 极小，更多诊断字段优先走 snapshot 扩展（避免下游 schema 绑定风险）
    - 代码：`src/scalim/events/_events.py`、`src/scalim/workflow/execute_controller.py`、`src/scalim/ob/presets/viz/workflow.py`

此外，仓库内有用于“性能印象”对比的可运行 notebook（非 benchmark）：
`notebooks/marimo/workflow_stage_scheduling_perf/demo_main.py`。

## Goals / Non-Goals

**Goals:**

- 引入一份残留风险清单（risk register），作为后续迭代/验收时的稳定入口（SSOT 预计落在 `openspec/specs/`）。
- 明确当前推荐策略的默认值与边界（默认 preset、术语、stage 折叠策略、可观测字段扩展策略）。
- 给出“何时必须更新 risk register”的触发条件，降低其过期概率。

**Non-Goals:**

- 不改变任何 runtime 行为（调度语义、stage 推导、事件结构均不改）。
- 不新增 benchmark / perf 套件；不把 notebook 结论升级为“严谨基准”。

## Decisions

1. **Risk register 作为 OpenSpec spec 落盘**：作为可被 OpenSpec 索引页发现的稳定入口，而不是停留在 proposal/change 目录或 commit message。
2. **默认策略与边界写进 risk register**：
   - `pipeline` 仍为默认；`stage_barrier` 为显式 opt-in，并明确其“可解释性优先”的 trade-off。
   - 对外只使用 `stage`（不引入 `wave` 等同义概念分叉）。
   - 内部 write nodes 的对外 `stage` 归因折叠到输入 demand 的 `stage`（更贴近用户视角）；如需更细粒度诊断，优先通过 snapshot 扩展而非改动既有事件 payload。
3. **可观测字段扩展策略**：新字段优先走 `viz snapshot`；仅在字段被证实需要“事件流强消费”时，才考虑扩展 workflow node 事件 payload，并明确稳定性/版本策略。

## Risks / Trade-offs

- **Risk register 过期风险**：文档不自带门禁，容易随实现演进而漂移。缓解：把更新触发条件写进 spec，并在 tasks 里明确验收口径与 gate（`just openspec-check` / `just qa`）。
- **性能风险难以在 spec 内完全量化**：吞吐/壁钟时间受 DAG 形态、资源与环境影响。缓解：保留可复现的“印象 notebook”，并强制区分“印象/趋势”与 benchmark。

## Migration Plan

- 在本 change 中新增/补全 delta specs（risk register）。
- 当进入实施/归档前：
  - 将 delta specs 同步到 `openspec/specs/`（作为 SSOT）。
  - 运行 `just gen-docs` 刷新 docs-site 的 OpenSpec 索引页（生成物/注入块禁止手改）。
  - 运行 `just openspec-check`（sanitize + validate）与 `just qa` 作为验收门禁。

## Open Questions

- 是否需要在 viz snapshot 中同时暴露 `struct_level`（拓扑层级）与折叠后的用户 `stage`，以降低“折叠隐藏执行细节”的排障摩擦？
- 是否需要为 `stage_barrier` 增加阶段级诊断字段（例如 stage 间 gap、barrier 等待解释）？如果要加，字段应该落在 snapshot 的哪个位置（meta / stage entries / node data）？

