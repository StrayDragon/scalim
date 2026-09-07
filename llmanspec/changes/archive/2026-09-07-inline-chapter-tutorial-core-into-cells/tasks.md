# Tasks: inline-chapter-tutorial-core-into-cells

> 单 change 收尾 cells-native「教程核心直接可见」：readme_suite 主路径内联（删 5 个纯主路径零件）
> → 机械化检查 → demo 对拍期望值可见化。迁移属机械改写（expand-contract：先内联后删旧），
> 每编号段 ≈ 一个 commit。金标准形态：本仓库既有 cells-native 章节（如 ch020_yaml_dsl_ads.py）。

Seam（已确认）：`run_chapter()` via registry / `just examples`（headless runner）+ `tests/integration/test_demo_big_data_report_chapters.py` 等 + `just gen-readme-examples --check`（README 漂移门）+ 新检查脚本 CLI 子进程；无 `.feature` 可执行场景、无 `bdd:` runner 段（examples-marimo 全 @human，沿用现有 pytest/examples gate 作为行为护栏）。

## 0. Specs landing（propose / 绑定分支，apply 前）

- [x] 0.1 `examples-marimo.feature` 新增 @req:r1113（cells 禁外部 `run_*()` 主路径委托 + 机械化检查，`run_chapter` 豁免）与 @req:r1114（对拍期望值 cells 可见：期望展示 + `chapter_result.details` 含 `expected*` 键；比对机制 MAY 留零件）；statement + GWT 双区；**不修改既有场景文本**
- [x] 0.2 commit specs（Specs landing）。DoD: `llman sdd show inline-chapter-tutorial-core-into-cells --json` → `readyToImplement=true`

## 1. readme_suite ch010_min_python 内联 [blocked-by: 0.2]

- [x] 1.1 `support/min_python.py` 主路径拆 cells：loader/派生函数 cell → `build_min_demand`（DemandIr 装配）cell → `PlanBuilder`/`RuntimeBindings` cell → engine.run cell → 期望展示 cell（3 行、`amount_x2=20.0`，教学 payload 不 hide_code）→ 断言/chapter_result cell
- [x] 1.2 删除 `support/min_python.py`；`inject.py` 的 `min_python` 指针区块改指 `chapters/ch010_min_python.py`
- [x] 1.3 DoD: `just examples`（readme suite）绿；`marimo check` 无 critical；`just gen-readme-examples --check` 绿

## 2. readme_suite ch020_min_yaml 内联 [blocked-by: 0.2]

- [x] 2.1 `support/min_yaml.py` 主体拆 cells：YAML 路径定位 cell → `RunOverrides`/`run` cell → 期望展示 cell（3 行、`methods={card,cash}`）→ 断言/chapter_result cell；保留 `min_yaml_loaders.py`（YAML loader_ref 路径稳定）
- [x] 2.2 删除 `support/min_yaml.py`
- [x] 2.3 DoD: 同 1.3（quickstart 注入区块内容不变）

## 3. readme_suite ch030_memory_compare 内联 + 快照助手迁移 [blocked-by: 0.2]

- [x] 3.1 naive/scalim 两条管线 + `relative_ratio` 拆 cells（`measure.py`/`counting_sink.py`/`knobs.py` 零件照用，RSS 口径不变）；期望展示（行数一致）
- [x] 3.2 `compare.py` 的 `load_snapshot`/`snapshot_path`/`relative_ratio`/`write_snapshot_from_live` 迁入唯一消费方 `render_chart.py`；删除 `compare.py`/`naive_baseline.py`/`scalim_path.py`
- [x] 3.3 `inject.py` 的 `naive`/`scalim` 指针区块改指 `chapters/ch030_memory_compare.py`
- [x] 3.4 DoD: `just gen-readme-examples` 重新生成 + `--check` 绿（README 注入区块与图资产随指针更新）；`just examples` 绿

## 4. 机械化检查 check-notebook-cells-native [blocked-by: 1.3, 2.3, 3.4]

- [x] 4.1 `scripts/check-notebook-cells-native.py`：AST 规则按 design D1（受限模块 `run_*` 导入名的 cells 内调用 → 违规；`run_chapter` 豁免；`# pragma: allow-cells-native-run-delegation` 白名单）；r1114 规则 = `make_chapter_result(details=<dict 字面量>)` 须含 `expected*` 键（`details` 为变量时静态不可判定不报）；违规样本 pytest `tests/governance/test_check_notebook_cells_native.py`（tmp_path fixture + 直接模块加载 seam）
- [x] 4.2 justfile `quick-check-only-py-no-test-gate` 链追加 `check-notebook-cells-native`
- [x] 4.3 DoD: 当前树 0 违规退出 0；fixture 违规样本可红（含 pragma 白名单可绿的用例）——pytest 6/6 绿

## 5. demo_big_data_report 对拍期望值可见化（r1114 面） [blocked-by: 0.2]

- [x] 5.1（实施记录）r1114 允许「期望字面量」形态：38 个对拍章节统一在 `chapter_result` cell 前插入 `expected = {...}` 字面量（逐章对齐 checks 语义）+ `print("expected:", ...)` 展示 + `details` 首键 `"expected"`；oracle/verify 零件签名零改动（pytest 兼容性天然保持）；行级期望表格渲染留作后续 UI 增强（details["verification"]/oracle details 已可 headless 定位）
- [x] 5.2 `chapters_of_yaml_dsl` 21 章全部补 `expected` 字面量 + 展示 + `chapter_result.details["expected"]`
- [x] 5.3 `chapters_of_ir`（details 为非字面量形态，静态不可判定，随 5.1 口径在后续 UI 增强覆盖）+ hooks 4 章 + public_api 13 章同 5.2 落地
- [x] 5.4 DoD: `just examples` 全绿（53/53）

## 6. 模板与全量收尾 [blocked-by: 4.3, 5.4]

- [x] 6.1 `_templates/cells_native_chapter.py` Cell 11 增加期望展示段落示范（对照 r1114）
- [x] 6.2 全量 DoD: `just qa` exit 0；`marimo check` 0 critical（改动章节零 error）；`llman sdd validate inline-chapter-tutorial-core-into-cells --strict --no-interactive` 绿
