# frontend/ 工具全量分析：能力、依赖面、可删性与删除影响

结论先讲清：`frontend/` 下的两套前端 **都不是** `src/scalim/` runtime 执行链路的硬依赖；删它们不会让 “YAML → IR → Plan → Execution” 这条主链路失效。它们的价值在于**作者体验**与**排障体验**，以及作为仓库门禁(`just qa`)的一部分。

当前前端体量(本地含 node_modules 时)：`du -sh frontend` 约 285M；是“精简磁盘与依赖”的最大收益点之一。

---

## 1) `frontend/scalim-yaml-dsl-editor/`：YAML DSL 编辑器

### 1.1 它提供什么能力

仓库自述：`frontend/scalim-yaml-dsl-editor/README.md`

- text-first 编辑器(基于 Monaco)
- schema 补全/hover/校验
- issues 面板(unknown fields/schema issues + 本地 semantic 规则)
- 可选 `semantic: exact`：通过 Pyodide 在浏览器里运行 Python 侧校验逻辑，对齐 `scalim-cli yaml-dsl validate`

### 1.2 它依赖什么“仓库内 SSOT”

1) canonical JSON schema(来源 SSOT)：

- `src/scalim/dsl/by_yaml/schema/demand.gen.json`
- `src/scalim/dsl/by_yaml/schema/workflow.gen.json`

2) editor schema 镜像(为前端打包内置与 runtime fallback)：

- `frontend/scalim-yaml-dsl-editor/src/schema/*.gen.json`
- `frontend/scalim-yaml-dsl-editor/public/schema/*.gen.json`
- build 后：`frontend/scalim-yaml-dsl-editor/dist/schema/*.gen.json`(来自 public)

同步入口：

- `just gen-yaml-dsl-editor-schema` → `scripts/gen-yaml-dsl-editor-schema.py`

漂移门禁：

- `just schema-drift-check` 会检查上述镜像文件是否有未提交变化(见 `justfile`)
- `scripts/check-yaml-dsl-editor-dist-schema.py` 会验证 dist 内 schema 与 canonical schema 一致(在 `just frontend-yaml-dsl-editor-check` 中调用)

### 1.3 它被哪些入口“强绑定”

如果你直接删除 `frontend/scalim-yaml-dsl-editor/`，至少会影响：

- `just frontend-yaml-dsl-editor-check`
- `just frontend-check`
- `just qa` (因为 `check:` recipe 依赖 `frontend-check`)
- `just gen-yaml-dsl-editor-schema` (生成入口失效)
- `just schema-drift-check` 中对 `frontend/scalim-yaml-dsl-editor/**/schema/*.gen.json` 的 `git diff` 检查需要删掉或改写
- 文档页：
  - `docs/doc/yaml-dsl/editor.md`
  - `docs/doc/getting-started/index.md`(工具入口索引里会指向 editor)
- `scripts/bump-versions.py`(会同时 bump 前端版本号：`frontend/scalim-yaml-dsl-editor/package.json`)

### 1.4 删除它，对 runtime 能力有什么“真实损失”

不会损失：

- YAML DSL 本身的解析/校验/编译/执行
- CLI 校验：`scalim-cli yaml-dsl validate|schema ...`
- JSON schema 生成：`just gen-yaml-dsl-schema`

会损失：

- 浏览器端的 YAML 作者体验(补全/hover/issues/visual)
- “不依赖本机 Python 环境”的轻量写配置入口
- `semantic: exact(Pyodide)` 这种“把 Python validator 搬到浏览器”的体验

### 1.5 更细粒度的精简建议(不必一刀切)

如果你的目标是“减维护成本、但保留基本作者体验”，建议优先按顺序考虑：

1) **把前端从 `just qa` 中拆出去**：保留代码，但 CI/默认门禁不跑 `frontend-check`。
2) **保留 schema 镜像与纯前端能力，删除 exact(Pyodide) 支持**：去掉 `public/pyodide`/wheel 相关脚本与 UI，依赖 `scalim-cli` 在本机做 exact。
3) **完全移出仓库**：把 editor 独立成外部 repo；本仓库仅保留 canonical schema 与 CLI 校验。

---

## 2) `frontend/scalim-viz/`：可视化回放 UI(Scalim Viz)

### 2.1 它提供什么能力

仓库自述：`frontend/scalim-viz/README.md`

输入是执行产物目录中的 JSON/JSONL：

- `viz_snapshot.json`：依赖图快照(来自 `ExecutionPlan.to_viz_graph_snapshot()`)
- `viz_events.jsonl`：编排级事件流(来自 `VizObserver`)
- `viz_trace.jsonl`：可选高频 trace(需要 `trace_enabled=true`)
- `viz_schedule_plan.json`：可选计划视角(adaptive fanout/fanin/屏障等结构)

### 2.2 产物从哪里来(不依赖前端)

1) snapshot：

- `src/scalim/planning/plan.py::ExecutionPlan.to_viz_graph_snapshot`
- `src/scalim/planning/viz.py`

2) events/trace：

- `src/scalim/ob/presets/viz.py::VizObserver`
- YAML DSL 可通过 `observability.viz` 配置启用(见 `src/scalim/dsl/by_yaml/runtime/observability.py`)

3) schedule plan：

- `src/scalim/planning/plan.py::ExecutionPlan.to_viz_schedule_plan`
- 生成脚本：`scripts/gen-viz-schedule-plan.py`

### 2.3 它被哪些入口“强绑定”

删除 `frontend/scalim-viz/` 会影响：

- `just frontend-scalim-viz-check`
- `just frontend-check`
- `just qa`(同上，默认包含 frontend-check)
- 文档页：`docs/doc/viz/scalim-viz.md` 与开发文档 `docs/doc/dev/devcontainer.md`
- `scripts/bump-versions.py`(会 bump `frontend/scalim-viz/package.json`)
- OpenSpec/变更文档里对前端路径的引用(属于文档层，不影响 runtime，但会让仓内 spec/arch 文档“指向不存在路径”)

### 2.4 删除它，对 runtime 能力有什么“真实损失”

不会损失：

- viz artifacts 的生成能力(事件/快照/trace/schedule plan 都在 Python 侧)

会损失：

- 本仓库内置的回放 UI(交互式排障与回放体验)

### 2.5 更细粒度的精简建议

按收益/风险排序：

1) **先把它从 `just qa` 拆出去**：保留源码，但默认门禁不要求 Node/pnpm。
2) **保留 artifacts 协议，UI 外置**：在 docs 中声明“UI 在外部 repo/另行安装”，本仓库只保留协议与 Python 产物生成。

---

## 3) `frontend/` 精简的最小改动点清单(供你估算工作量)

如果你要“删掉整个 frontend/”，最低需要同步修改/删除：

- `justfile`：
  - 移除 `frontend-*` recipes
  - `check:` recipe 不再依赖 `frontend-check`
  - `schema-drift-check` 中移除对 `frontend/scalim-yaml-dsl-editor/**/schema/*.gen.json` 的 diff gate
- `scripts/`：
  - `scripts/gen-yaml-dsl-editor-schema.py`、`scripts/check-yaml-dsl-editor-dist-schema.py`(若不再需要 editor)
  - `scripts/bump-versions.py` 的 targets 列表(若仍保留脚本)
- `docs/doc/`：
  - `docs/doc/yaml-dsl/editor.md`
  - `docs/doc/viz/scalim-viz.md`
  - 以及导航页(如 `docs/zensical.toml` 中的菜单项)
- `openspec/specs/` 与 `openspec/changes/**`：
  - 主要是文档引用更新(不更新也能跑，但仓内规范会变“漂移/失真”)

