## 0. 合并变更(本 change 内承接 Phase 1)

- [x] 0.1 将 `marimo-demo-big-data-report-chapters` 的 delta spec 合并到本 change（`specs/` 下保留两份 capability spec）
- [x] 0.2 移除独立 change 目录: `openspec/changes/marimo-demo-big-data-report-chapters/`
- [x] 0.3 更新 `openspec/changes/README.md`：只保留一个合并后的 change 入口描述

## 0.4 Coverage 报告（替代手工维护 coverage_matrix）

- [x] 0.4.1 新增生成脚本：`scripts/gen-marimo-coverage.py`
- [x] 0.4.2 生成 SSOT 报告：`notebooks/marimo/marimo_coverage.gen.md`
- [x] 0.4.3 删除 `notebooks/marimo/coverage_matrix.md` 并更新引用（notebooks/specs/changes）
- [x] 0.4.4 增加 `just gen-marimo-coverage` / `just marimo-coverage-drift-check` 并纳入 `just gen`/`just qa` 漂移门禁

## 1. notebooks/marimo 目录重组(删除后重写)

- [x] 1.1 新增 `notebooks/marimo/index.py`(Marimo hub): 说明示例分类(demo_/example_/tutor_)与 `just examples`/coverage 报告的关系
- [x] 1.2 固化 notebook 写作模板(目标/SSOT/如何跑/结果展示/失败定位),并将现有 notebooks 对齐该模板
- [x] 1.3 保持 `notebooks/marimo/run_examples.py` 为 headless runner(不改为 Marimo),并在 `index.py` 中说明其定位
- [x] 1.4 删除/清理历史遗留目录: `notebooks/marimo/examples/`（无引用则移除）

## 2. demo_big_data_report：章节化教学入口（Marimo）(方案 A: 1:1 对齐 SSOT chapters)

- [x] 2.1 新增 `notebooks/marimo/demo_big_data_report/chapters/` 目录
- [x] 2.2 将 `notebooks/marimo/demo_big_data_report/demo_main.py` 调整为 hub/index: 增加章节导航 + 保留“一键跑完章节”汇总 + 保留 skill markers
- [x] 2.3 守护 canonical YAML SSOT 路径不变: `by_yaml_dsl/ecommerce_report.yaml` 与 `ecommerce_report_fragments.yaml` 不移动不改名
- [x] 2.4 新增章节 notebooks(文件名以 `<chapter_id>.py` 结尾; 可带 `01_` 前缀):
  - [x] `chapters/01_basics.py`(调用 `run_basics`)
  - [x] `chapters/02_yaml_dsl.py`(展示 canonical YAML 片段 + 调用 `run_yaml_dsl`)
  - [x] `chapters/03_workflow_yaml.py`(展示 workflow fixture 片段 + 调用 `run_workflow_yaml`)
  - [x] `chapters/04_sinks.py`(调用 `run_sinks`)
  - [x] `chapters/05_memory_opt.py`(调用 `run_memory_optimization`)
  - [x] `chapters/06_observability.py`(调用 `run_observability`)
  - [x] `chapters/07_parallel_mode.py`(调用 `run_parallel_mode`)
  - [x] `chapters/08_diagnostics.py`(调用 `run_diagnostics`)
  - [x] `chapters/09_guardrails.py`(调用 `run_guardrails`)
  - [x] `chapters/10_loader_retry.py`(调用 `run_loader_retry`)
  - [x] `chapters/11_output_composition.py`(调用 `run_output_composition`)
  - [x] `chapters/12_derived_set_aggregations.py`(调用 `run_derived_set_aggregations`)

## 3. shared 下沉到 `packages/scalim-misc`（notebook-support helpers）

- [x] 3.1 新增 `scalim_misc.notebook_support.pathing`：统一 repo_root 注入与示例资源路径解析（避免每本 notebook 重复写 `sys.path` hack）
- [x] 3.2 新增 `scalim_misc.notebook_support.results_view`：将 `ChapterResult/ExampleResult.details` 结构化为可渲染 rows（不依赖 marimo）
- [x] 3.3 新增 `scalim_misc.notebook_support.yaml_excerpt`：从 YAML SSOT 摘录局部片段用于教学展示（不参与执行; 不依赖 marimo）

## 4. example_public_api：教学化与一致性（Marimo）

- [x] 4.1 对齐写作模板: 为 `notebooks/marimo/example_public_api/*.py` 补齐“SSOT 路径 + gate 入口 + 失败定位”段落
- [x] 4.2（可选）将 `example_public_api` 的章节展示升级为更可读的 Marimo UI（例如 tabs/table/callout），不改变底层 SSOT 实现

## 5. headless runner 与 pytest 复用（集成对拍作为单测补充）

- [x] 5.1 扩展 `notebooks/marimo/run_examples.py` 支持按 suite/章节过滤运行（保持默认行为不变）
- [x] 5.2 为 `demo_big_data_report` 增加至少 1 个 pytest 复用点（调用同一套 SSOT 章节/对拍逻辑），作为单测补充

## 6. Drift gate（防止示例体系回退）

- [x] 6.1 更新 `tests/test_notebook_examples_readme_paths.py`：守护 `notebooks/marimo/index.py` 与关键套件目录/章节 notebooks 的存在性
- [x] 6.2（可选）增加轻量检查：阻止将 marimo 依赖引入 `packages/scalim-misc` 的 notebook-support helpers

## 7. 验证

- [x] 7.1 通过 `just examples`
- [x] 7.2 通过 `just qa`
- [x] 7.3 通过 `just openspec-check`
