## Why

当前 `scalim-viz` 的主入口仍是单次 run(通常是 demand/adaptive)回放：用户能看到某个 run 的依赖图、时间线与计划视角，但看不到 **workflow 本身** 作为业务模块编排层的结构。workflow 使用方往往只能拿到一组彼此分离的 run 目录，难以做到"先定位 workflow 模块拓扑，再回溯到某个 demand 深分析，然后保持上下文返回继续对照"。

我们希望把"定位 + 回溯"变成 workflow-first 的默认体验，并把一次 workflow 执行导出为一个可携带目录包(目录内部天然联动)，降低分享与复盘成本。

## What Changes

- **New**: 定义 workflow replay bundle 的最小契约,但尽量复用既有 run 目录结构
  - bundle 仍然是一个包含 `scalim-viz/<run_id>/viz_*.{json,jsonl}` 的目录
  - 约定存在一个 workflow scope 的 run: `scalim-viz/workflow/`
    - `viz_snapshot.json` 表达 workflow 拓扑(节点以业务模块/demand 为主)
    - `viz_events.jsonl` 表达 workflow 自己的时序(节点开始/结束等)
  - workflow demand 节点通过 `node.data.demand_run_id` 指向同 bundle 内的某个 demand run id(目录名)
  - bundle 内部联动 MUST 仅依赖 run id 与相对目录结构,不得依赖绝对路径
- **Modified**: 引入 workflow-first 的回放入口(前端)
  - 当检测到 `workflow` run 存在时,UI MUST 默认选中并展示 workflow 画布(拓扑优先)
  - 点击 workflow demand 节点: inspector 展示 workflow 上下文信息,并提供"进入 demand 视图"
  - demand 视图复用既有 graph/timeline/adaptive 能力
  - 返回 workflow 视图时 MUST 保留用户上下文:
    - viewMode、playbackIndex、选中节点、stage filter、focus、viewport
  - 优化 workflow 节点表现,保持现有视觉语言,但能一眼区分其 scope/可 drill-down 性
- **Cleanup**: 移除 dev-only workflow proto 入口/页面,改为真实 bundle 数据验证

### Recommended Direction (MVP)

- 先做 **workflow-first + drill-down demand replay** 的两层结构,不把 workflow DAG 和 demand 字段依赖图混到同一张图里。
- workflow 图的默认心智以"业务模块"优先:MVP 以 demand 节点为主,资源关系通过资源节点或 typed edges 表达。
- bundle 目录保持"一个目录,内部多个 run(含 workflow)"的稳定布局,使 `frontend/scalim-viz/` 能同时支持:
  - 打开带 workflow 的 bundle 并默认进入 workflow
  - 继续打开旧的单 run demand replay(无 workflow 时保持原行为)

## Capabilities

### New Capabilities
- `workflow-replay-bundle`: 定义 workflow 作为一个特殊 run 的导出契约(目录结构、workflow snapshot/events、workflow->demand linking 字段)。

### Modified Capabilities
- `flow-visualization`: 扩展可视化输出与前端交互,支持 workflow-first 入口、workflow node/resource 命名、以及从 workflow demand 节点 drill-down 到既有 demand 视角。

## Impact

- 受影响代码（预期）:
  - `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py`
  - `src/scalim/ob/presets/_internal/viz_*.py`
  - `frontend/scalim-viz/src/domain/**`
  - `frontend/scalim-viz/src/ui/**`
- 文档与规范:
  - SSOT: `openspec/specs/**`, `docs/doc/viz/scalim-viz.md`, `frontend/scalim-viz/README.md`
  - Generated / injected（禁止手改）:
    - `docs/doc/specs/openspec-index.gen.md`
    - 其他 `.gen.*` 页面与 `BEGIN/END AUTOGEN:*` 区块
  - 生成入口:
    - `just gen-docs`
    - `just openspec-check`
- 兼容性:
  - 现有单 run replay 入口 MUST 继续可用
  - 既有 child run 文件名契约 SHOULD 保持不变，避免 demand 视角回放逻辑整体重写
