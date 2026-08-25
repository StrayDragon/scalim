# language: zh-CN
# capability: cli-yaml-dsl-viz-compile
# purpose: TBD - created by archiving change c0-yaml-dsl-viz-compile-cli. Update Purpose after archive. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: cli-yaml-dsl-viz-compile

  @req:r1 @human
  场景: Demand YAML 静态导出 viz 产物
    - `scalim-cli` MUST 提供命令： `scalim-cli yaml-dsl viz compile --type demand <demand.yaml> --output-dir <dir>` 该命令 MUST 在不执行任何 loader 的前提下，基于静态编译得到的 `ExecutionPlan` 写出： - `<dir>/viz_snapshot.json` - `<dir>/viz_schedule_plan.json`

  @req:r2 @human
  场景: Demand 静态导出不依赖业务运行时
    - `--type demand` 的静态导出 MUST NOT 触发 runtime linking（例如 import 用户模块、解析 loader callable、要求 allowlist）。

  @req:r3 @human
  场景: Workflow YAML 静态导出 scalim-viz bundle
    - `scalim-cli` MUST 提供命令： `scalim-cli yaml-dsl viz compile --type workflow <workflow.yaml> --output-dir <dir>` 该命令 MUST 在 `<dir>/scalim-viz/` 下写出： - `workflow/viz_snapshot.json` - `<run_id>/viz_snapshot.json` - `<run_id>/viz_schedule_plan.json` - `bundle_manifest.json` 其中 workflow snapshot 的 demand 节点 MUST 携带 `demand_run_id=<run_id>`（用于前端下钻到对应 run 目录）。

  @req:r4 @human
  场景: Workflow demand 路径别名默认来自 scalim.yaml
    - 当项目存在 `scalim.yaml yaml_dsl.import_roots[*].alias` 时，`--type workflow` MUST 将该 alias 映射用于 workflow `runs[*].demand` 的路径解析，并提供默认 `@ -> project_root`（若未显式声明 `@`）。

  @req:r5 @human
  场景: 失败时返回非 0 并输出可诊断错误
    - 当输入 YAML 无法读取、解析、校验或无法生成 `ExecutionPlan` 时，命令 MUST： - 以非 0 退出码退出 - 输出包含文件路径与错误原因的可诊断信息到 stderr
  @req:r1 @human
  场景: 成功导出-demand-产物
    - 必须成立：当 用户执行 `scalim-cli yaml-dsl viz compile --type demand demo.demand.yaml --output-dir .tmp/viz_demo`；那么 目录 `.tmp/viz_demo/` 下存在 `viz_snapshot.json` 与 `viz_schedule_plan.json`
    当 用户执行 `scalim-cli yaml-dsl viz compile --type demand demo.demand.yaml --output-dir .tmp/viz_demo`
    那么 目录 `.tmp/viz_demo/` 下存在 `viz_snapshot.json` 与 `viz_schedule_plan.json`
  @req:r2 @human
  场景: 引用不可-import-的-loader-仍可导出
    - 必须成立：当 demand YAML 中 `main_source.loader`/`sources.*.loader` 引用一个语法合法但不可 import 的 Python reference；那么 `viz compile --type demand` 仍能生成 `viz_snapshot.json` 与 `viz_schedule_plan.json`
    当 demand YAML 中 `main_source.loader`/`sources.*.loader` 引用一个语法合法但不可 import 的 Python reference
    那么 `viz compile --type demand` 仍能生成 `viz_snapshot.json` 与 `viz_schedule_plan.json`
  @req:r3 @human
  场景: 成功导出-workflow-bundle
    - 必须成立：当 用户执行 `scalim-cli yaml-dsl viz compile --type workflow demo.workflow.yaml --output-dir .tmp/viz_bundle`；那么 `.tmp/viz_bundle/scalim-viz/` 下包含 `workflow/viz_snapshot.json`、每个 `run_id/` 子目录下的 `viz_snapshot.json` 与 `viz_schedule_plan.json`，以及 `bundle_manifest.json`
    当 用户执行 `scalim-cli yaml-dsl viz compile --type workflow demo.workflow.yaml --output-dir .tmp/viz_bundle`
    那么 `.tmp/viz_bundle/scalim-viz/` 下包含 `workflow/viz_snapshot.json`、每个 `run_id/` 子目录下的 `viz_snapshot.json` 与 `viz_schedule_plan.json`，以及 `bundle_manifest.json`
  @req:r4 @human
  场景: 支持-语法解析-demand-路径
    - 必须成立：当 workflow YAML 的某个 run 以 `@/path/to/demand.yaml` 声明 demand 路径，且项目存在可定位的 `scalim.yaml`；那么 `viz compile --type workflow` 能成功解析该 demand YAML 并为该 `run_id` 写出静态 viz 产物
    当 workflow YAML 的某个 run 以 `@/path/to/demand.yaml` 声明 demand 路径，且项目存在可定位的 `scalim.yaml`
    那么 `viz compile --type workflow` 能成功解析该 demand YAML 并为该 `run_id` 写出静态 viz 产物
  @req:r5 @human
  场景: yaml-非法时失败
    - 必须成立：当 用户执行 `viz compile` 且入口 YAML 存在语法/语义错误；那么 命令退出码非 0，且 stderr 包含错误原因与入口 YAML 路径
    当 用户执行 `viz compile` 且入口 YAML 存在语法/语义错误
    那么 命令退出码非 0，且 stderr 包含错误原因与入口 YAML 路径
