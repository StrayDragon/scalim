## 1. Spec / Contracts

- [x] 1.1 确认并固化 vizevent 命名: `output_target_finished` + `node_ref=output_target:{target_id}`(与 spec 一致)
- [x] 1.2 为 `output_target` 节点与 `composed_from` 边补充最小可读 label/data 约定(用于 UI 展示)

## 2. Python: VizEventStream 事件映射

- [x] 2.1 在 `src/scalim/ob/presets/_internal/viz_handlers.py` 增加 `OutputTargetEndEvent -> output_target_finished` 映射(含 payload 字段与 duration_ms 转换)
- [x] 2.2 为 `OutputTargetEndEvent` 映射补充最小单测/回归验证(如本仓有对应测试入口则补齐;否则以示例回放数据验证)

## 3. Python: VizGraphSnapshot 输出目标节点增强

- [x] 3.1 扩展 `VizObserver.from_plan(...)` 支持传入 `output_composition` 并在快照中追加 `output_target:*` 节点
- [x] 3.2 为 direct/derived 输出目标追加 `composed_from` 边(字段集合规则见 spec);meta/audit 节点仅创建 node
- [x] 3.3 对增强后的 `nodes/edges` 做稳定排序(避免输出顺序漂移)
- [x] 3.4 更新 `src/scalim/execution/run_ir.py` 与 `src/scalim/dsl/by_yaml/runtime/introspection.py` 的调用点传入 `output_composition`

## 4. Frontend: Graph 节点适配

- [x] 4.1 新增 `frontend/scalim-viz/src/components/OutputTargetNode.svelte` 并注册到 `frontend/scalim-viz/src/ui/panels/GraphCanvas.svelte`
- [x] 4.2 更新 `frontend/scalim-viz/src/domain/graph/layout.ts` 的 node size/type order(如需要)以提升输出节点布局可读性

## 5. Frontend: run 标签展示

- [x] 5.1 在 `frontend/scalim-viz` 中读取并缓存 `viz_snapshot.json.meta.viz.run_name/env`
- [x] 5.2 在 `frontend/scalim-viz/src/ui/panels/TopBar.svelte` 展示 run_name/env(主标签)并在缺失时 fallback 到 run_id

## 6. Frontend: output_target_finished 展示

- [x] 6.1 为 `output_target_finished` 增加事件摘要与详情渲染(行数/耗时/错误/禁用/路径/sheet/错误信息)
- [x] 6.2 在 inspector/timeline 中支持查看该事件并可从输出目标节点快速定位最近一次事件

## 7. Docs / Examples / Verification

- [x] 7.1 更新 `docs/doc/viz/scalim-viz.md` 补充 workflow 多 runs 推荐 `run_name` 用法与 outputs 解释口径
- [x] 7.2 (可选) 更新/新增 `artifacts/scalim-viz/examples/` 示例数据覆盖 `output_target_finished` 与 `meta.viz.run_name/env`
- [x] 7.3 运行 `openspec validate scalim-viz-workflow-adaptations --type change --strict --no-interactive`
- [x] 7.4 运行 `just openspec-check`、`just gen-docs`、`just qa` 确认无漂移与质量门禁通过
