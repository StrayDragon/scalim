# Design: inline-chapter-tutorial-core-into-cells

## D1. 主路径委托 vs 零件复用的机械边界

AST 全量扫描（2026-09-07，main@5803cdc9）结果分三类：

| 类别 | 实例 | 处置 |
|------|------|------|
| `run_*` 主路径委托（3 处） | `run_min_python` / `run_min_yaml` / `run_compare` | 内联进 cells，删除零件 |
| `build_*` 共享 fixture 装配（38 处） | `build_ecommerce_model` / `build_minimal_public_api_ir` / `build_upload_payload` / `build_test_config_small` | **保留**（r1111 零件：多章共享的测试数据模型/mock；IR 章节 Model 构建虽是 ch010_basics 的教学内容，但 8 章 IR 章共用同一 300+ 行模型，逐章复制不可维护） |
| 工具/展示零件 | `notebook_support.*`、`yaml_excerpt`、`results_view` | 保留（r682 已约束 headless 纯 Python） |

**决策**：机械检查只锁 `run_*` 名字模式（r497 字面义），`build_*` 不入检——避免 38 处误报，也守住 r159（YAML loader_ref 模块路径稳定，`min_yaml_loaders.py`、`scalim_misc.demo_*.loaders` 不可挪动）。

检查器规则（`scripts/check-notebook-cells-native.py`）：
- 扫描对象：`notebooks/marimo/**/chapters*/ch*.py`（章节 notebook）。
- 违规 = 某个 `@app.cell` 内存在 `Call`，其被调名解析到 `ImportFrom` 导入、导入名匹配 `run_*`（`run_chapter` 豁免）、且来源模块匹配 `notebooks.*.support.*` / `scalim_misc.demo_*` / `scalim_misc.examples.*`。
- 白名单：文件级 `# pragma: allow-cells-native-run-delegation`（沿用 `check-noqa-c901.py` 惯例）。
- 退出码非零 = 存在违规；输出 `违规文件 → 被调名 ← 来源模块` 行。
- 接线：`just quick-check-only-py-no-test-gate` 链尾追加 `check-notebook-cells-native`。

## D2. 期望值的形态：可见 ≠ 字面量化

`verification.py` 的期望结果由 `_PythonJoinEngine().build_all_expected()` 参考实现**计算**得出（非静态字面量），且被多章 + pytest 共享。把它复制/硬编码进每章 cells 是反模式。

**决策**（r1114 的落地形态）：
- 期望**值**可见：对拍章节新增期望展示 cell——调 oracle 的期望访问器（现有 `build_all_expected` / 各场景模块补齐 `expected_*` 访问器）取得期望行，用 `mo.ui.table` / markdown 代码块渲染，与实际输出对照。
- 期望**留存**：`chapter_result["details"]` 增加 `expected*` 键（headless/pytest 可定位期望快照）。
- 比对**机制**（join 参考实现、`diff_first_mismatch`、CSV 比对）留在 `scalim_misc` 零件，签名向后兼容。

由此 r1114 的机械可查代理：对拍章节 `chapter_result["details"]` MUST 含 `expected` 前缀键（检查器第二步，浅结构校验）。cells 内渲染属 review-checklist 人工复核项。

## D3. readme_suite 删留清单与快照助手去向

- 删：`min_python.py`(68) / `min_yaml.py`(50) / `compare.py`(60) / `naive_baseline.py`(37) / `scalim_path.py`(99)。主路径合计 ~250 行，逐 cell 展开后无信息损失。
- 留：`min_yaml_loaders.py`（YAML loader_ref 引用模块路径）、`min_yaml_example.yaml`（README quickstart 区块的文本 SSOT）、`knobs.py`（r983 可调旋钮合约）、`measure.py`/`counting_sink.py`（RSS 测量零件）、`inject.py`/`render_chart.py`（生成管线）。
- `compare.py::load_snapshot`/`snapshot_path`/`relative_ratio`/`write_snapshot_from_live`：唯一消费方是 `render_chart.py`（README 记忆对比图渲染），迁入该文件，不新建模块。

## D4. README 指针重定向

`inject.py::_snippet_blocks` 调整：
- `min_python` 指针：`support/min_python.py` → `chapters/ch010_min_python.py`
- `naive` / `scalim` 指针：`support/naive_baseline.py` / `support/scalim_path.py` → `chapters/ch030_memory_compare.py`
- `min_yaml` quickstart 区块不变（YAML + loaders 两文件均保留）。

governance-readme-examples r980（仅注入区块）/ r982（漂移检查）/ r984（示例可跑）均不受影响；改后必须跑 `just gen-readme-examples` 并过 `--check`。

## D5. marimo 形态要点（沿用 r497/r1112 既有合约）

- 每个教学步骤一个 cell；import 在 cells 内；末段 `chapter_result` + 薄 `run_chapter()`。
- 期望展示 cell 用 `hide_code=True` 与否由教学价值决定（ch010 期望本身是教学payload，不隐藏）。
- 本 change 不需要 `@app.function`/`app.setup`（无跨 notebook 复用内联代码的需求；README 生成链只依赖 inject.py 指针与 YAML 文本，不 import 章节 cells）。

## D6. 备选方案回顾（为何不做）

- **全量内联 fixtures/oracle**：与 YAML loader_ref 模块路径约束冲突 + 多章共享数据复制 → 不可维护，否决。
- **只改 readme_suite**：留下「期望值不可见」缺口与检查缺口，用户已决策全套件单 change，否决。
- **把 `build_*` 一并锁死**：38 处误报、破坏 r1111 零件边界，否决（见 D1）。
