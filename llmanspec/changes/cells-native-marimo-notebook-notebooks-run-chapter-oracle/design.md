# Design: cells-native marimo notebook 形态推广

## 背景与目标

约 42/53 章 notebook 是「薄壳」：执行逻辑住在模块级 `run_*()` 或 `support/*.py`，cells 只做
`import → call → 显示 PASS/FAIL`，打开 notebook 无法观察机制；部分章节 cell 层甚至存在
NameError（如 ch010/ch020/ch130 的自引用 `chapter_result` 残留）。目标是不动三条 gate
（`just examples` / `report-notebooks-coverage` / `gen-readme-examples`），把 notebook
改造成「执行真相在 cells、oracle 是薄适配层」的 cells-native 形态。

## 核心设计决策

1. **Oracle 契约不变，实现方式反转**：
   - Before: `run_<id>()` 函数持有执行真相（模块级），cells 调用它 → UI/真相分离，可漂移。
   - After: 执行真相在 marimo cells 内逐步展开；模块级仅保留 `run_chapter()` 薄适配层
     （`app.run()` → 提取 `defs["chapter_result"]`）。
   - `ChapterRegistry._safe_run()` 已支持 dict 结果——**零 runner 改动**。
2. **零件 vs 装配边界**（对应新 spec 规则 r1111）：
   - 留 support/：fixtures 数据、mock 基础设施、通用 Observer/Hook 类、YAML 片段资源。
   - 进 cells：装配（接线/注入点/运行顺序）、scalim 调用、断言展开、中间产物展示。
3. **交互与 headless 同源**（对应新 spec 规则 r1112）：
   - UI 控件始终创建展示；headless/script 模式用控件默认值自动执行全流程；
     昂贵步骤才用 `run_button`+`mo.stop` 手动触发。
   - 交互重跑断言须幂等（如 server 侧用「存在匹配」而非「精确计数」），
     避免控件变化重跑时状态累积误判（ch010 示范已落地此模式）。
4. **readme suite 特殊约束**：`support/inject.py` + `render_chart.py` 是 README 注入与
   SVG 资产的生成 SSOT（`governance-readme-examples` 合约），只做展示层增强，
   生成管线零改动。

## 文档/生成边界

- 生成物：`report-notebooks-coverage.py` 输出（覆盖报告）；README 注入区块与 SVG
  （`just gen-readme-examples`）；`just gen-docs` 站点页面。本 change 不新增生成物。
- 手工文件：章节 notebooks（`notebooks/marimo/**/chapters/ch*.py`）、
  `llmanspec/specs/examples-marimo/examples-marimo.feature`（SSOT）、tasks.md/proposal.md。
- 无 `.gen.` 文件、无 AUTOGEN 注入区块涉及。

## 迁移顺序（tasks.md 对应）

ch010 样板已合入 main → 脚手架（notebook_support helper）→ hooks_events 剩余 4 章 →
yaml_dsl 21 章（3 批）→ public_api 13 章 → readme 展示层 → 全量验证。
按 suite 分批 commit，每批 DoD 见 tasks.md。

## Drift gate 方案

- 行为护栏（不变）：`just examples`（headless runner 全 suite）、
  `tests/integration/test_example_hooks_events_scenarios.py`、
  `just check-notebooks-coverage`（AST import 统计，cells 内 import 仍计入）。
- 形态护栏：`marimo check` 无 critical（修复跨 cell 变量重名/分支表达式）。
- spec 护栏：`llman sdd validate --all --strict --no-interactive`。
- 风险：大章节（ch164 等 400+ 行）拆分工作量大，分批提交降低 review 负担；
  readme suite 受生成合约约束，改动前置 `just gen-readme-examples --check` 验证。