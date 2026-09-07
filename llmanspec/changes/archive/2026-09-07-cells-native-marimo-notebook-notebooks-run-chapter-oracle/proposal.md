---
depends_on: []
branch: sdd/cells-native-marimo-notebook-notebooks-run-chapter-oracle
base_sha: d1b5cb4565ccc0f5c9c0414c6cd984c00484ef63
checkpointed: true
rules_edit_acked: true
checkpoint_sha: d1b5cb4565ccc0f5c9c0414c6cd984c00484ef63
---

## Why

`notebooks/marimo/` 下 53 章章节 notebook 中约 42 章采用「薄壳」形态：全部教学逻辑住在模块级 `run_*()` 函数（或 `support/*.py`）里，marimo cells 只是 `import → call → 显示 PASS/FAIL`。用户在浏览器打开 notebook 只能看到结果，无法观察机制/中间产物/运作过程，丧失交互笔记本价值。

根因：对拍 SSOT 被实现成「逻辑住在 oracle 函数里」，而正确形态（仓库已有 pilot：`chapters_of_ir/*`、`example_stage_scheduling_perf/chapters/*`，共 11 章 cells-native）是「oracle 是薄适配器，逻辑住在 cells 里」——`run_chapter()` = `app.run()` + 提取 `defs["chapter_result"]`。基础设施已就绪（`ChapterRegistry._safe_run()` 已支持 dict `chapter_result`），无需改动任何 gate。

目标：在保持 `just examples` / `report-notebooks-coverage` / `gen-readme-examples` 三条 gate 不变的前提下，确立 cells-native 为唯一编写模式，让 notebook 兼具教学可观察性与集成对拍 oracle 价值。

## What Changes

- **Specs landing：修订 `examples-marimo` 的 @req:r497（statement + GWT 双区）**：
  「Marimo notebooks 必须是薄封装（调用 SSOT 入口函数）」→「章节执行真相位于 notebook cells，SSOT 入口为薄适配层」；
  新增 @req:r1111（零件与主路径边界：fixtures/mock/类 MAY 留 support，装配与断言 MUST 在 cells）与 @req:r1112（交互控件始终展示、script 模式同源）。
  修改既有 @human 场景，frontmatter 已设 `rules_edit_acked: true`。
- **确立 cells-native 编写模式规范**（随 spec r497/r1111/r1112 落地成为合约）：
  - 每个教学步骤一个 cell（配置 → 模型 → plan → 执行 → 中间结果 → 断言 → 汇总）
  - 依赖 import 放 cells 内（`app.run()` 新建 `__main__` 上下文）
  - 末尾 cell 产出 `chapter_result = {"passed", "summary", "details"}`
  - 模块级只保留 `app = marimo.App(...)` + 薄 `run_chapter()`（`app.run()` + `defs["chapter_result"]`）
- **按序迁移薄壳章节**：
  1. `example_hooks_events_scenarios`（5 章，pilot 示范：主流程从 `support/*.py` 搬进 cells，support 只留 fixtures/http_mock/可复用类）
  2. `demo_big_data_report/chapters_of_yaml_dsl`（21 章，模块级 `run_*()` 拆渐进 cells）
  3. `example_public_api_suite`（13 章，ch164 等 400+ 行拆分；清理 `ch130` cell 内自引用残留 bug：`chapter_result = {"passed": chapter_result["passed"], ...}`）
  4. `example_readme_suite`（3 章，保持 `support/inject.py` + `render_chart.py` 生成管线不变，仅增强展示层）
- **交互性增强**（marimo 官方 skill 指南）：UI 控件永远显示、script 模式仅换数据源；昂贵章节用 `mo.ui.run_button` + `mo.stop`；`mo.cache`/`mo.persistent_cache` 缓存 fixtures；`mo.ui.tabs` 组织步骤/中间结果/断言详情/YAML 源码；`mo.ui.table`、altair/plotly 可视化中间产物。
- **support/ 重新定位**：保留 fixtures/数据生成、oracle 验证函数、可复用 Observer/Hook 类、mock 基础设施、YAML 资源；装配/接线/调用/断言过程搬进 cells（零件留 support，装配进 cells）。
- **Gate 硬约束保持**：`just examples`（registry `run_chapter()` 入口）、`report-notebooks-coverage.py`（AST 提取 import，cells 内 import 仍统计）、`just gen-readme-examples`（README 注入/SVG 资产）均不改变。
- **降成本脚手架**：`scalim_misc.notebook_support` 增加 `make_chapter_result(...)` helper 或标准模板，配套编写规范。

## Capabilities

- notebooks 具备渐进式探索 + 就地可视化 + 单 cell 重跑定位能力
- 交互模式下用户可调参数（slider/number/dropdown）触发响应式 DAG 重跑；script/headless 模式自动用默认值跑通
- 章节打开即可观察完整装配过程（observer 接线、mock、yaml 写入、断言展开）

## Impact

- **不破坏**：`just examples` 对拍门禁、notebook 覆盖门禁、README 示例注入合约、pyproject marimo runtime 配置（lazy/auto_instantiate=false）
- **见效顺序**：hooks_events 一章示范（前后对比）→ 全 suite 迁移 → yaml_dsl/public_api 大章拆分 → readme 展示层增强
- **风险**：大章节（ch164 等）拆分工作量大，需分批提交；readme suite 受生成合约约束，改动需谨慎