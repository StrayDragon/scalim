## Context

目前为 demand/workflow YAML 生成可被 `frontend/scalim-viz` 回放的 Viz 产物，需要维护较长的 wrapper 脚本（仓库内已有 `scripts/gen-viz-data.py`、`scripts/gen-viz-workflow-bundle.py` 等）。这些脚本中最常见、最稳定的部分其实是“静态结构导出”：

- `ExecutionPlan.to_viz_graph_snapshot()` → `viz_snapshot.json`
- `ExecutionPlan.to_viz_schedule_plan()` → `viz_schedule_plan.json`

另一方面，CLI 运行环境与业务运行环境往往不一致（例如业务要求 Python 3.6 + Django/DB，而 `scalim-cli` 面向 3.10+ dev/tooling）。因此本变更的核心设计约束是：**导出必须尽量静态化，不依赖业务运行时，不 import 用户模块**。

## Goals / Non-Goals

**Goals:**

- 新增 `scalim-cli yaml-dsl viz compile`，用于静态导出 Viz 产物（不执行 loader / 不生成事件流）。
- 仅保留强约束参数形态（无额外可选参数）：
  - `--type demand|workflow`
  - `<yaml>`（demand 或 workflow YAML 路径）
  - `--output-dir <dir>`
- `--type demand`：在 `<output-dir>/` 写出 `viz_snapshot.json` + `viz_schedule_plan.json`。
- `--type workflow`：在 `<output-dir>/scalim-viz/` 写出 workflow 静态 bundle（含 `bundle_manifest.json` 与每个 run 的静态产物）。
- 默认行为可在缺失业务运行时（数据库、Django、下游包）时运行，专注于“结构依赖图 + 静态调度视角”。

**Non-Goals:**

- 不提供 `viz run`（不执行 `run()`，不输出 `viz_events.jsonl`/`viz_trace.jsonl`/`perf.json`）。
- 不保证配置可运行（例如 loader 引用是否可 import、签名是否匹配）；`viz compile` 只保证静态结构可视化。
- 不提供 `--init-vars`/`--allowed-modules`/`--path-aliases` 等额外参数；尽量复用项目内既有约定（例如 `scalim.yaml`）。

## Decisions

### CLI 入口与参数收敛

- 在 `packages/scalim-cli/` 的 `yaml-dsl` 命令树下新增 `viz compile` 子命令。
- 参数保持最小集：`--type`, `<yaml>`, `--output-dir`；其它行为通过“隐式默认”实现（例如读取 `scalim.yaml`）。

### Demand 静态编译路径（不 runtime linking）

- 使用 `YamlDemandLoader` 加载并校验 YAML（含 `$import` 展开）。
  - `$import` 的可读根目录边界沿用现有策略：若存在 `scalim.yaml yaml_dsl.import_roots`，允许根目录由其扩展；否则仅允许入口 YAML 所在目录。
- 使用 `ConfigToIRConverter` + `PlanBuilder` 构建 `ExecutionPlan`，但必须避免对业务侧 `init_vars` 与运行时函数的依赖：
  - 对 `{$init_var: <name>}` 采用“占位注入”策略：在 CLI 内部提供一个 `Mapping`，对任意 `<name>` 都返回占位值，以便 params 模板在转换阶段可被解析而无需真实的运行时变量。
  - 不调用 `scalim.dsl.yaml_dsl.runtime.compile/run`，从而避免 allowlist/security 与 runtime linking（import 用户模块）这条路径。

### Workflow 静态 bundle 产物

- 解析 workflow YAML 得到 `WorkflowConfig`，并构建一个最小的 `WorkflowIr`（仅包含 demand 节点与依赖边；resources 可省略或写空路径）。
- demand YAML 路径解析：
  - 默认从 workflow YAML 所在目录解析相对路径；
  - 若存在 `scalim.yaml`，复用其中的 `yaml_dsl.import_roots[*].alias` 作为 workflow demand path 的 alias 映射，并补充默认 `@ -> project_root`（使 `@/` 语法可用）。
  - `allowed_yaml_roots` 默认使用 `project_root`（若存在）作为上界，避免 demand 路径逃逸。
- 输出目录结构与仓库既有脚本对齐：对 `<output-dir>` 先执行 `normalize_output_dir()`，保证产生 `<output-dir>/scalim-viz/` 根目录。
- 写出：
  - `scalim-viz/workflow/viz_snapshot.json`（workflow scope 静态依赖图，节点包含 `demand_run_id=<run_id>` 以支持下钻）
  - `scalim-viz/<run_id>/viz_snapshot.json`
  - `scalim-viz/<run_id>/viz_schedule_plan.json`
  - `scalim-viz/bundle_manifest.json`（paths 优先写为相对当前工作目录的 POSIX 路径，以适配 `frontend/scalim-viz` DevTools `/?bundle=` 方式）

## Risks / Trade-offs

- **占位 init_vars** → 可能掩盖 params 模板中的真实类型/取值问题；但该命令定位为“结构可视化”，不承担运行期可执行性验证。
- **无额外参数** → 某些工作流项目若依赖自定义 path_aliases/allowed_yaml_roots，可能需要通过 `scalim.yaml` 约定或改写 workflow YAML 来适配。
- **workflow resources 不完整** → 若省略 resources 或写空 path，UI 中资源节点信息会不完整；但不影响“拓扑 + demand 下钻 + 计划视角”的核心价值。

