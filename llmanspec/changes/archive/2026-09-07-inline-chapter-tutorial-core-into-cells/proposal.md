---
depends_on: []
branch: sdd/inline-chapter-tutorial-core-into-cells
base_sha: 5803cdc9cf2560a5a1c20704c6ed6cc2136c1ea9
checkpointed: true
checkpoint_sha: 5803cdc9cf2560a5a1c20704c6ed6cc2136c1ea9
---

## Why

42 章 cells-native 化（2026-09-07 归档）后，「打开 notebook 即可观察教程核心」仍残留两个缺口与一个检查缺口：

1. **主路径跳转**：`example_readme_suite` 全部 3 章（新用户入门第一站）把执行主路径整体委托给 support 零件——ch010 调 `support/min_python.py::run_min_python()`（整个 Python IR 装配在零件里）、ch020 调 `run_min_yaml()`、ch030 调 `run_compare()`（naive/scalim 两条对比管线都在零件里）。这违反 r497 字面义（「MUST NOT 通过调用外部模块级 `run_*()` 函数来执行」），但现有 gate 无机械化检查，违规可静默复发。
2. **期望值不可见**：demo_big_data_report 各对拍章节的 cells 调 `verify_*` oracle 后只渲染 PASS/FAIL，期望结果（"正确答案长什么样"）封装在 `scalim_misc` oracle 模块内部（如 `_PythonJoinEngine.build_all_expected()`），读者无法在 notebook 内对照期望与实际。
3. **机械检查缺口**：AST 全量扫描证实当前 `run_*` 主路径委托恰好 3 处（均在 readme_suite）；`build_*` 类共享 fixture 装配（ecommerce model、public_api fixtures、http_mock payload）属 r1111 允许的零件，须与主路径委托区分开。

## What Changes

- **Specs landing（examples-marimo 新增两条 @req，不修改既有场景文本）**：
  - r1113：章节 notebook cells MUST NOT 把执行主路径委托给外部模块级 `run_*()` 函数（来源限 `notebooks.*.support.*` / `scalim_misc.demo_*` / `scalim_misc.examples.*`；SSOT 入口 `run_chapter()` 豁免）；配套机械化检查门禁。
  - r1114：对拍章节的期望结果 MUST 在 cells 内可见（期望表渲染 + `chapter_result.details` 携带 `expected*` 键）；比对机制（参考实现/diff 函数）MAY 留在零件模块。
- **readme_suite 三章主路径内联**：
  - `ch010_min_python`：loader/派生函数/`DemandIr` 装配/`PlanBuilder`/`RuntimeBindings`/engine.run/断言逐 cell 展开；期望（3 行、`amount_x2=20.0`）在 cells 内。
  - `ch020_min_yaml`：YAML 路径定位/`RunOverrides`/`run`/断言进 cells；期望（3 行、`methods={card,cash}`）在 cells 内。
  - `ch030_memory_compare`：naive 与 scalim 两条管线 + RSS 对比逻辑进 cells；期望（行数一致）在 cells 内。
  - 删除纯主路径零件：`support/min_python.py` / `support/min_yaml.py` / `support/compare.py` / `support/naive_baseline.py` / `support/scalim_path.py`。
  - 保留零件：`min_yaml_loaders.py`（`min_yaml_example.yaml` 的 loader_ref 引用其模块路径，路径稳定）、`min_yaml_example.yaml`、`knobs.py`、`measure.py`、`counting_sink.py`、`inject.py`、`render_chart.py`、`chart_snapshot.json`。
  - `compare.py` 的快照助手（`load_snapshot`/`snapshot_path`/`relative_ratio` 等）迁入唯一消费方 `render_chart.py`。
  - `inject.py` README 指针区块改指章节 notebook（min_python → ch010、naive/scalim → ch030）+ `just gen-readme-examples` 重新生成；governance-readme-examples（r980–r986）合约不变——注入来源、漂移检查、可运行 SSOT 均保持，指针目标属内容层细节。
- **demo_big_data_report 对拍期望值可见化（r1114 面）**：
  - oracle/场景模块补充期望访问器（`verification.py` 已有 `build_all_expected`；ads/ecommerce_rank_score/support/temporal/derived 等按需补齐），签名向后兼容 pytest 消费方。
  - 各对拍章节新增期望展示 cell（`mo.ui.table`/代码块渲染期望行）+ `chapter_result.details` 增加 `expected*` 键。
- **机械化检查**：新增 `scripts/check-notebook-cells-native.py`（AST 扫描：cells 内调用来自受限模块的 `run_*` 导入名 → 违规；`run_chapter` 豁免；沿用 `# pragma:` 白名单惯例兜底），接入 `just quick-check-only-py-no-test-gate` 检查链。
- **模板**：`_templates/cells_native_chapter.py` 增加期望展示段落示范。

## Capabilities

- examples-marimo：新增 r1113/r1114；既有 r497/r1111/r1112/r401 等不变
- governance-readme-examples：合约不变（无需 specs landing）

## Impact

- **Gate 不变**：`just examples`（`run_chapter()` registry 入口）、`check-notebooks-coverage`（cells 内 import 仍统计）、`gen-readme-examples` 漂移门全部保持，仅 README 注入内容随指针更新。
- **见效**：新用户打开 readme_suite 任意章节即见完整装配与期望值；demo 对拍章节可见期望 vs 实际对照。
- **风险**：
  - ch030 内联后 RSS 测量须继续走 `measure.py`/`counting_sink.py` 零件，演示数值口径不回退；
  - 检查脚本按 `run_*` 名字模式识别，未来零件若用 `run_` 前缀命名可能误报，靠 pragma 白名单兜底；
  - oracle 期望访问器重构须保持 pytest 既有调用签名兼容。
- **Seam（测试边界）**：复用既有 harness seam——`run_chapter()` via registry（`just examples` + `tests/integration/test_demo_big_data_report_chapters.py` 等）；`gen-readme-examples --check` 漂移门；新检查脚本以 CLI 子进程为 seam（违规样本用内联字符串 fixture 断言退出码与报告行）。