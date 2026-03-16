## 1. Spec & Governance Sync

- [x] 1.1 在实现前确认 `demo_big_data_report` 新增 public API 章节的最终 `chapter_id` 列表与命名（与 spec 保持一致）
- [x] 1.2 根据实现细节回填/调整本 change 的 delta specs（`specs/marimo-notebooks-examples-suite/`、`specs/marimo-demo-big-data-report-chapters/`、`specs/testing-quality/`）

## 2. Notebooks SSOT Layout (user-first)

- [x] 2.1 为 `demo_big_data_report` 增加 notebooks 侧章节 registry（例如 `notebooks/marimo/demo_big_data_report/chapters/registry.py`），集中管理章节清单与 `run_all_chapters()/run_selected_chapters()`
- [x] 2.2 将 `notebooks/marimo/demo_big_data_report/demo_main.py` 改为调用 notebooks 侧 registry，并保留“章节导航 + 一键跑完汇总”
- [x] 2.3 在每个章节 notebook 中引入统一的 SSOT 入口函数（例如 `run_<chapter_id>()`），并确保 import-time 不执行重逻辑（runner/pytest 可安全导入）

## 3. Migrate Demo Chapters from `scalim-misc` to Notebooks

- [x] 3.1 将 `packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/*` 的教学主流程迁移到对应章节 notebooks（保留 fixture/oracle/工具在 `scalim-misc`）
- [x] 3.2 更新章节 notebooks：用 Marimo UI 组件展示过程与结果（table/tabs/callout/form 等），并保留 deterministic 对拍语义
- [x] 3.3 清理 `packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/*`（迁移后删除或降级为仅 fixture/oracle/工具入口）

## 4. Public API Coverage (merge + delete suite)

- [x] 4.1 删除 `notebooks/marimo/example_public_api/`，并将其能力并入 `demo_big_data_report/chapters/`（按稳定入口模块 `__all__` 组织）
- [x] 4.2 为每个稳定入口模块新增/迁移一个章节 notebook：`scalim.dsl.by_yaml` / `scalim.spec.ir` / `scalim.planning` / `scalim.execution` / `scalim.ob`
- [x] 4.3 在每个 public API 章节的 SSOT 入口中增加 `__all__` 覆盖断言：缺失符号时 fail-fast 并输出缺口集合
- [x] 4.4 增加扩展点演示章节（hook/observer/events/components 注入等）并纳入 `just examples`
- [x] 4.5 清理 `packages/scalim-misc/src/scalim_misc/examples/public_api/*` 与其 harness（迁移后删除或收敛为 fixtures/oracle/工具函数）

## 5. Headless Runner & Pytest Rewire

- [x] 5.1 更新 `notebooks/marimo/run_examples.py`：改为导入 notebooks 侧 registry/章节 SSOT 入口执行，并保持 `--suite/--chapter/--list` 等过滤能力
- [x] 5.2 删除或重写 `tests/test_example_public_api_suite.py`（改为覆盖新的 public API 主线章节）
- [x] 5.3 更新 `tests/test_demo_big_data_report_chapters.py`：改为复用 notebooks 侧 registry/章节 SSOT，并保留可选章节运行能力
- [x] 5.4 更新 `tests/test_notebook_examples_readme_paths.py`：守护新目录结构与章节存在性（含 public API 章节）

## 6. Coverage Report & Drift Gates

- [x] 6.1 更新 `scripts/gen-marimo-coverage.py`：映射口径改为 notebooks 侧 SSOT（并移除对 `example_public_api`/`scalim-misc` SSOT 的硬编码）
- [x] 6.2 运行 `just gen-marimo-coverage` 刷新 `notebooks/marimo/marimo_coverage.gen.md` 并确保 `just marimo-coverage-drift-check` 通过

## 7. Docs Updates (paths + guidance)

- [x] 7.1 更新 docs 中对 `example_public_api` 的引用与运行指引（将入口指向新主线章节/runner）
- [x] 7.2 运行 `just gen-docs`（如涉及 injected blocks / `.gen.` 页面漂移）并确保 docs drift gate 通过

## 8. Verification

- [x] 8.1 通过 `just examples`（输出 PASS/FAIL 可定位，失败时退出码非零）
- [x] 8.2 通过 `just qa`
- [x] 8.3 通过 `just openspec-check`
