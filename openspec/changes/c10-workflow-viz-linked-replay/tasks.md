## 1. Bundle Contract & Writer

- [x] 1.1 定义 workflow replay bundle 的最小 SSOT 契约(复用 run 目录结构):`scalim-viz/workflow/` + `scalim-viz/<demand_run_id>/...`,以及 workflow snapshot 中的 `node.data.demand_run_id` linking 规则。
- [x] 1.2 在 workflow 级导出链路中实现“一次导出得到完整 bundle”的 writer/协调器,确保用户不需要手工收集多个 run 目录。
- [x] 1.3 约束 `demand_run_id` 不得指向不存在的 child run:当 child run 缺失 `viz_snapshot.json`/`viz_events.jsonl` 时必须省略该字段,并提供可读降级提示信息(由前端展示)。

## 2. Workflow Snapshot & Event Projection

- [x] 2.1 新增 workflow snapshot 构建逻辑(输出到 `scalim-viz/workflow/viz_snapshot.json`):生成 workflow demand 节点、共享资源节点与 `depends_on` / `writes_to` 等边,并保持稳定排序。
- [x] 2.2 workflow demand 节点在 snapshot 中必须携带 `kind="workflow_demand"` 与 `demand_run_id`,并可选携带 stage 信息用于 staged 布局。
- [x] 2.3 为 workflow 级事件补齐 viz 投影(输出到 `scalim-viz/workflow/viz_events.jsonl`),确保 `workflow_*` 事件使用稳定的 workflow node/resource `node_ref` 命名空间。
- [x] 2.4 保持 child replay 使用既有 `viz_snapshot.json` / `viz_events.jsonl` / `viz_trace.jsonl` / `viz_schedule_plan.json` 契约，避免 demand drill-down 另起一套格式。

## 3. Frontend Workflow-First UX

- [x] 3.1 扩展 `frontend/scalim-viz/src/domain/`:当目录中存在 `workflow` run 时,默认选中并展示 workflow scope,并与旧的单 run replay 入口兼容。
- [x] 3.2 实现 workflow -> demand drill-down:在 workflow demand 节点 inspector 中提供“进入 demand 视图”;在 demand scope 提供“返回 workflow”,并恢复 workflow 状态(viewMode/playbackIndex/selection/stage filter/focus/viewport)。
- [x] 3.3 优化 workflow demand 节点表现:保持现有视觉语言,但能区分于普通 derived 节点,并展示 stage_id/drill-down 线索。
- [x] 3.4 补齐 workflow 事件在 timeline/inspector 中的可读解释(事件文案、摘要字段、jump tokens),并覆盖并发窗口等常见 workflow 情况。
- [x] 3.5 移除 dev-only prototype 入口(例如 `?proto=workflow`),用真实 bundle 数据验证 workflow-first + drill-down(并把验证路径写入 README)。

## 4. Docs, Examples, Gates

- [x] 4.1 更新 SSOT 文档 `docs/doc/viz/scalim-viz.md` 与 `frontend/scalim-viz/README.md`,说明 workflow bundle 目录结构(`scalim-viz/workflow/`)、workflow-first 入口与 drill-down 口径(`demand_run_id`)。
- [ ] 4.2 如需同步生成页或 injected blocks，运行 `just gen-docs`；禁止手改 `.gen.*` 与 `BEGIN/END AUTOGEN:*` 区块。
- [x] 4.3 补齐测试：bundle 目录布局、linking 规则(demand_run_id)、workflow node/resource 命名稳定性、workflow -> demand drill-down 状态保持。
- [ ] 4.4 运行 `openspec validate --all --strict --no-interactive`、`just openspec-check` 与相关 `just qa` 门禁，确认工件与实现无漂移。
