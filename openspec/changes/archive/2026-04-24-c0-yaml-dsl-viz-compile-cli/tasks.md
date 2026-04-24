## 1. CLI Wiring

- [x] 1.1 在 `packages/scalim-cli/src/scalim_cli/yaml_dsl.py` 注册 `yaml-dsl viz compile` 子命令，并收敛参数为 `--type demand|workflow <yaml> --output-dir <dir>`
- [x] 1.2 统一错误输出到 stderr，并确保失败时返回非 0（包含入口 YAML 路径 + 可诊断原因）

## 2. Demand 静态导出

- [x] 2.1 在 CLI 侧实现“占位 init_vars Mapping”（任意 key 都视为存在并返回占位值），避免 `{$init_var: ...}` 触发缺失错误
- [x] 2.2 实现 demand 静态编译链路（`YamlDemandLoader` → `ConfigToIRConverter` → `PlanBuilder` → `ExecutionPlan`），并确保不走 runtime linking（不 import 用户模块）
- [x] 2.3 `--type demand` 输出到 `<output-dir>/`：写出 `viz_snapshot.json` + `viz_schedule_plan.json`

## 3. Workflow 静态 bundle 导出

- [x] 3.1 读取项目 `scalim.yaml`，提取 `yaml_dsl.import_roots[*].alias` 形成 workflow demand path alias 映射，并补齐默认 `@ -> project_root`（若未显式声明）
- [x] 3.2 `--type workflow`：解析 workflow YAML、解析每个 run 的 demand 路径并对每个 run 静态编译 demand 计划
- [x] 3.3 对齐既有脚本目录约定：对 `<output-dir>` 调用 `normalize_output_dir()`，在 `<output-dir>/scalim-viz/` 下写出：
  - `workflow/viz_snapshot.json`
  - `<run_id>/viz_snapshot.json`
  - `<run_id>/viz_schedule_plan.json`
- [x] 3.4 生成 `bundle_manifest.json`（version=1, directoryLabel, runs[{id,path}]；path 使用 POSIX 且相对 repo root/workdir 的路径，兼容 `frontend/scalim-viz` DevTools `/?bundle=` 加载）

## 4. Tests

- [x] 4.1 demand: 引用不可 import 的 loader 仍能生成 `viz_snapshot.json` + `viz_schedule_plan.json`
- [x] 4.2 workflow: 支持 `@/` 语法解析 demand 路径，且 bundle 目录结构 + `bundle_manifest.json` 生成成功
- [x] 4.3 CLI: `scalim-cli yaml-dsl --help` / `... viz --help` 包含新增命令（smoke）

## 5. Docs & QA

- [x] 5.1 更新 `packages/scalim-cli/README.md`，补充 `yaml-dsl viz compile` 用法示例与产物目录说明
- [x] 5.2 验收：运行 `just openspec-check`；并运行 `pytest` 覆盖新增 CLI 测试用例（不应触碰任何 `*.gen.*` 或 AUTOGEN 注入块）
