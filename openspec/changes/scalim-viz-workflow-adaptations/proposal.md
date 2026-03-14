## Why

随着 YAML DSL 的 `outputs`(多 sheet/派生汇总)与 workflow YAML(`run_workflow`)落地,`scalim-viz` 的回放视角缺少两类关键信号: **每个输出目标的写出统计/失败状态** 与 **可读的 run 标识**(run_name/env),导致多输出/多 runs 的定位与对拍成本显著上升。

因此需要补齐一条“最小闭环”:让可视化事件流能表达 outputs 的结果,并让前端能解释/展示 run 的语义标签,以支持 workflow 场景的稳定排查与回归对比。

## What Changes

- 在 VizEventStream(`viz_events.jsonl`)中补齐 **输出目标结束事件**:
  - 将执行层的 `OutputTargetEndEvent` 映射为新的 `event_type`: `output_target_finished`
  - 为与现有 `run_finished`/`batch_finished` 后缀一致,`event_type` 采用 `output_target_finished`
  - payload 至少包含: `target_id`、`row_count`、`duration_ms`、`disabled`、`error_count`、`sheet_name`/`output_path`(若存在),并包含 `error_type`/`error_message`(若存在)
  - 保持为低频“编排级事件”(不进入 trace 文件),并保持 `vizevent/v1` 的结构兼容
- 在 `frontend/scalim-viz/` 中补齐 **run 语义展示**:
  - 以 `viz_snapshot.json` 的 `meta.viz.run_name` 作为主展示标签,`run_id` 作为 fallback(两者可能不同;`run_id` 侧重唯一性,`run_name` 侧重语义标识);并展示 `meta.viz.env`(若存在)
  - 在依赖图中展示 `output_target:*` 节点,并在 timeline/inspector 中展示 `output_target_finished` 摘要(便于理解 composed outputs 的每个目标是否成功、写了多少行、落到哪个 sheet/路径)
- 文档补齐:
  - 在 viz 文档中明确: workflow/多 runs 推荐设置 `observability.viz.run_name` 为稳定标识(可直接使用 workflow run id),并说明 UI 对 outputs/workflow 的解释口径

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `flow-visualization`: 扩展 VizEventStream 事件映射以覆盖 `OutputTargetEndEvent`,并要求前端在回放时可解释并展示 run 标签与 outputs 目标级统计。

## Impact

- 受影响范围(预期):
  - Python: `src/scalim/ob/presets/_internal/viz_handlers.py`(新增输出目标结束事件映射)
  - 前端: `frontend/scalim-viz/src/domain/*` + `frontend/scalim-viz/src/ui/panels/*`(展示 run_name/env 与 outputs 目标级事件摘要)
  - 文档: `docs/doc/viz/scalim-viz.md`(补充 workflow/outputs 的使用与解释)
- 兼容性:
  - 新增 `event_type` 为向后兼容扩展;旧 UI 可忽略未知事件,新 UI 将消费并展示该事件
