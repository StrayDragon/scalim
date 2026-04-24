## Why

当前为一个 demand/workflow YAML 生成可被 `frontend/scalim-viz` 回放的 Viz 产物，需要编写并维护大量与可视化无关的 wrapper 脚本（组装 options、注入 viz_config、补写 schedule plan、处理输出目录等）。这导致：

- scalim 仓库内与下游业务仓库重复实现同一套样板逻辑，维护成本高；
- 仅想在 code review / 本地编译阶段查看依赖结构与静态调度层视图时，也不得不具备完整运行时环境；
- `viz_schedule_plan.json` 作为前端计划视角的重要输入，需要额外手工补齐，不够“一键化”。

## What Changes

- 新增 CLI 子命令：`scalim-cli yaml-dsl viz compile`，用于静态导出 Viz 产物（不执行 loader，不产生事件流）。
- 仅保留最小且强约束的参数形态：
  - `scalim-cli yaml-dsl viz compile --type demand <demand.yaml> --output-dir <dir>`
  - `scalim-cli yaml-dsl viz compile --type workflow <workflow.yaml> --output-dir <dir>`
- `--type demand`：
  - 解析并编译 demand YAML 到 `ExecutionPlan`（跳过 runtime linking / 不 import loader callable）。
  - 在 `<output-dir>/` 写出：
    - `viz_snapshot.json`（依赖图）
    - `viz_schedule_plan.json`（Adaptive 计划视角，静态 fanout/fanin/屏障）
- `--type workflow`：
  - 解析并编译 workflow YAML 到 workflow IR。
  - 在 `<output-dir>/scalim-viz/` 下写出静态 bundle（不包含 events）：
    - `workflow/viz_snapshot.json`（workflow scope 依赖图）
    - `<run_id>/viz_snapshot.json`（每个 demand run 的依赖图）
    - `<run_id>/viz_schedule_plan.json`（每个 demand run 的计划视角）
    - `bundle_manifest.json`（用于 `frontend/scalim-viz` DevTools `/?bundle=` 自动加载）

## Capabilities

### New Capabilities

- `cli-yaml-dsl-viz-compile`: 为 demand/workflow YAML 提供一键静态导出 `viz_snapshot.json` + `viz_schedule_plan.json` 的 CLI 能力，并生成可被 `scalim-viz` 直接加载的 workflow bundle 目录结构。

### Modified Capabilities

<!-- none -->

## Impact

- 影响范围主要在 `packages/scalim-cli/` 的 CLI 命令注册、实现与测试。
- 不改变 `src/scalim/` 运行时行为边界（仍需兼容 Python 3.6）；该功能定位为 dev/tooling（CLI Python 3.10+）。

