## Context

随着 YAML DSL 的 `outputs`(多目标/多 sheet/派生汇总)与 workflow 多 runs(`run_workflow`)落地,当前 `scalim-viz` 回放存在两个缺口:

- **输出目标级结果不可见**: 执行层已产生 `OutputTargetEndEvent`(每个 target 的行数/耗时/错误/禁用),但 VizObserver 未将其映射到 `viz_events.jsonl`,前端也无法展示.
- **多 runs 缺少稳定语义标签**: `VizObserverConfig.run_name/env` 已写入 `viz_snapshot.json.meta.viz`,但前端未展示;用户只能靠目录名/`run_id`(时间戳)辨识 runs.

本变更目标是做“最小闭环补全”:在 **不改变既有 vizevent/vizgraph 结构** 的前提下,让 viz 能表达 outputs 的结果,并让 UI 用 `run_name/env` 解释 workflow 多 runs.

约束:
- Python 运行时需兼容 3.6.
- 文档治理: 不手改任何 `.gen.*` 文件与 `BEGIN/END AUTOGEN:*` 注入区块;修改 SSOT 后用 `just gen-docs` 刷新.

## Goals / Non-Goals

**Goals:**
- 将 `OutputTargetEndEvent` 映射为新的编排级 vizevent: `output_target_finished`.
- 在 VizGraphSnapshot 中增加 `output_target:*` 节点与 `composed_from` 边,让依赖图可定位输出目标.
- 前端以 `run_name` 为主标签展示 run,并展示 `env`;缺失时 fallback 到 `run_id`.
- 前端在 timeline/inspector 展示 `output_target_finished` 的摘要(含 `output_path` 全路径与 `error_message`).

**Non-Goals:**
- 不引入 workflow 级跨 run 聚合视角/对拍视角(例如多 runs 合并时序图).
- 不新增高频输出事件(如每行写出事件)与不改变 trace 分流策略.
- 不重构 `vizgraph/v1` 的既有节点/边语义(仅追加输出相关节点/边).

## Decisions

### 1) vizevent 命名与结构

- 新事件 `event_type` 采用 `output_target_finished`,与既有 `run_finished`/`batch_finished` 后缀一致.
- `node_ref` 采用:
  - `node_ref.type="output_target"`
  - `node_ref.id="output_target:{target_id}"`
- payload 字段:
  - 必含: `target_id`, `row_count`, `error_count`, `duration_ms`, `disabled`
  - 可选: `output_path`, `sheet_name`, `error_type`, `error_message`
- `duration_ms` 由 `OutputTargetEndEvent.duration`(秒)转换为毫秒整数(与现有事件对齐).

### 2) VizGraphSnapshot 增量建模策略

`ExecutionPlan.to_viz_graph_snapshot()` 目前仅覆盖 plan/fields/sources/loaders/stages,不包含 outputs.

为避免将输出语义侵入规划层,输出目标节点采用 **“快照增强(augment)”** 策略:
- 在 `VizObserver.from_plan(...)` 创建快照后,当存在 `output_composition` 时,对 snapshot 进行增量追加:
  - nodes: 追加 `output_target:{target_id}`(type=`output_target`)节点
  - edges: 对 direct/derived 目标追加 `composed_from` 边(`field:* -> output_target:*`)
  - meta/audit sheet(若存在)也创建 output_target 节点;边可省略
- 追加后对 nodes/edges 做稳定排序(按 `id`/`(source,target,type)`),避免输出顺序漂移导致 docs/examples 对拍困难.

选择该策略的理由:
- 仅修改 `viz` 子系统,避免 `planning/*` 的领域职责扩大.
- 变更点集中,便于回滚与兼容旧示例.

### 3) 前端展示策略

- **run 标签**:
  - 优先使用 `viz_snapshot.json.meta.viz.run_name` 作为主标签
  - 缺失时使用 `run_id`
  - `meta.viz.env` 存在时展示
  - 当 `run_name` 与 `run_id` 不一致时,UI 仍应能在详情处查看/复制 `run_id`(便于文件定位/对拍)
- **输出目标节点**:
  - 新增 `OutputTargetNode` 组件,用于渲染 type=`output_target` 的节点
  - inspector 中展示该节点的目标信息与最近一次 `output_target_finished` 事件摘要
- **事件摘要**:
  - 为 `output_target_finished` 增加摘要渲染(行数/耗时/错误/禁用/路径/sheet/错误信息)

## Risks / Trade-offs

- [隐私泄露风险] `error_message` 与 `output_path` 可能包含敏感信息 → 由调用方决定是否写入(现阶段按需求展示);后续可考虑引入可控脱敏/截断策略或在 UI 提供隐藏开关.
- [图可读性] outputs 节点与 `composed_from` 边可能引入边数量膨胀 → 最小实现先只连 direct/derived 的输入字段;后续再评估折叠/聚合/按 target 过滤能力.
- [run_name 重复] 不同 runs 可能共享同一 `run_name` → UI 以 `run_id` 作为唯一定位 fallback,并在详情处展示二者.

## Migration Plan

- 后端/前端均为向后兼容追加:
  - 新增 `event_type` 不影响旧 UI(未知事件可忽略).
  - 新增 `output_target` 节点与 `composed_from` 边不影响旧 UI(未知节点类型将以默认样式呈现;新 UI 将提供专用节点).
- 文档与示例:
  - 在手写文档中补充 workflow 推荐用法(建议 `run_name=workflow run id`).
  - 如需更新回放示例,以 `just gen-docs`/`just qa` 漂移门禁兜底.

## Open Questions

- 是否需要为 meta/audit sheet 补充边(例如 `output_target:* -> output_target:meta`)以表达“统计/审计依赖”?最小实现先不做边,后续按 UI 可读性再评估.
