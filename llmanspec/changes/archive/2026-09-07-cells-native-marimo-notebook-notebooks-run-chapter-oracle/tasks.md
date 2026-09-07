# Tasks: cells-native marimo notebook 形态推广

> 迁移是「每 suite 一批机械改写」的大范围重构，按 expand-contract 排序分批提交，
> 不强拆垂直切片。每个编号段 ≈ 一个 commit。示范样板已合入 main：
> `notebooks/marimo/example_hooks_events_scenarios/chapters/ch010_post_export_upload.py`
> （commit 9c37da14），后续章节以其为金标准。

Seam（已确认）：`ChapterRegistry.run_selected_chapters` / `just examples`（headless runner）+ `tests/integration/test_example_hooks_events_scenarios.py` + `marimo check`；无 `.feature` 可执行场景、无 `bdd:` runner 段（本 spec 全 @human，沿用现有 pytest/examples gate 作为行为护栏）。

## 0. Specs landing（propose / 绑定分支，apply 前）

- [x] 0.1 修订 `examples-marimo` 的 @req:r497（statement + GWT 双区）：薄封装 → 「执行真相位于 notebook cells，SSOT 入口为薄适配层」；新增 @req:r1111（零件/主路径边界）与 @req:r1112（交互控件始终展示 + script 同源）
- [x] 0.2 commit specs（Specs landing）。DoD: `llman sdd show cells-native-marimo-notebook-notebooks-run-chapter-oracle --json` → `readyToImplement=true`

## 1. 脚手架 — commit `feat(notebook_support): cells-native 章节模板助手`

- [x] 1.1 `scalim_misc.notebook_support` 增加 `make_chapter_result(...)`（统一 `{"passed","summary","details"}` 组装 + `details_to_rows` 兼容校验），docstring 写明 cells-native 契约
- [x] 1.2 可选：生成 `chapters/ch01x_template.py` 模板（16-cell 骨架：教学目标 → imports → 控件 → 零件 → fixtures → options → run → 断言 → chapter_result）
- [x] 1.3 DoD: `marimo check` 模板 0 critical；`just examples` 不回归（模板不入 registry，仅文档用途）

## 2. 迁移 example_hooks_events_scenarios 剩余章节 — commit `refactor(notebooks): hooks_events ch020-050 cells-native 化`

- [x] 2.1 ch020_precheck_route_sync_async：主流程入 cells（修复 cell 内自引用 `chapter_result[...]` NameError）
- [x] 2.2 ch030_upload_retry：主流程入 cells（含 503 重试观察点）
- [x] 2.3 ch040_pre_use_batch_size：主流程入 cells（batch_size 交互滑块）
- [x] 2.4 ch050_workflow_viz_finished：主流程入 cells（viz 事件流展示）
- [x] 2.5 删除各章 support/*.py 中被搬空的主流程；保留 fixtures.py/http_mock.py
- [x] 2.6 DoD: `marimo check` 无 critical；`just examples`（suite 过滤）5/5；`pytest tests/integration/test_example_hooks_events_scenarios.py` 绿

## 3. 迁移 demo_big_data_report/chapters_of_yaml_dsl（21 章）— 分批 commit

- [x] 3.1 首批 5 章（ch010/ch020/ch030/ch040/ch050）：模块级 `run_*()` 拆为渐进 cells（fixtures/oracle 保留在 `scalim_misc.demo_big_data_report`）
- [x] 3.2 第二批 8 章（ch060-090 + 调试 061-066 分组）
- [x] 3.3 第三批 8 章（ch100-150）
- [x] 3.4 DoD: `just examples` 主线 suite 全绿；抽查 `marimo check` 无 critical

## 4. 迁移 example_public_api_suite（13 章）

- [x] 4.1 ch130/ch135/ch150/ch160：拆分（ch130 顺带清理 cell 内自引用 `chapter_result` 残留）
- [x] 4.2 ch162-ch166（output write layout / lookup chunking / resources / source catalog）
- [x] 4.3 ch170-ch184（ob / hooks_events / event type groups / sinks pandas）
- [x] 4.4 DoD: `just examples` public_api suite 全绿；Tier1 entrypoint 覆盖 gate（`just check-only-py` 相关项）不降级

## 5. example_readme_suite 展示层增强（不动生成管线）

- [x] 5.1 三章 cells 内展示中间结果（naive vs scalim 对比数据表/knobs），`support/inject.py` + `render_chart.py` 与 `just gen-readme-examples` 管线零改动
- [x] 5.2 DoD: `just gen-readme-examples`（--check）绿；`just examples` readme suite 全绿

## 6. 全量验证

- [x] 6.1 `just examples`（全 suite）绿；`just check-notebooks-coverage` 绿
- [x] 6.2 `just qa` 绿；`marimo check` 章节抽查无 critical。DoD: 全部门禁绿，进入 `llman-sdd-verify`