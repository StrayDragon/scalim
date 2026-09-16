---
name: scalim-notebooks-expert
description: >
  Scalim 仓库 marimo notebooks（唯一教程套件 demo_big_data_report 的三轨章节：chapters_of_yaml_dsl / chapters_of_ir / chapters_of_scenarios，含 README 第一口 ch005/ch010/ch020）
  的 "cells-native 内联" 改写标准模式。当需要把章节 notebook 从"薄壳调用库 builder / 蓝盒装配"
  改写成"读者打开即可在 cells 内看到怎么写"时使用。涵盖：cells-native 内联原则、模型窥视、
  章节结果契约、可复用零件边界、配套门禁与验证命令。
compatibility: Requires Python 3.10+, uv, ruff, marimo (notebooks), just (gate entry).
metadata:
  project: scalim
  version: "1.0"
---

# Scalim Notebooks Expert：cells-native 内联改写模式

## 背景与核心原则

仓库契约（`llmanspec/specs/examples-marimo.feature` `@req:r497`/`r1111`/`r1112`/`r1113`/`r1114`）
要求：章节 notebook 的 **scalim 装配、运行、断言展开 MUST 在 marimo cells 内可见**，让读者打开
notebook 即可观察"怎么写"，而不是跳进 `scalim_misc` 库实现。只有真正的**可复用零件**
（fixtures 数据、mock 基础设施、通用 Observer/Hook 类、YAML 片段资源）可留在 `support/` 或
受控库模块。

### 蓝盒问题（要消除的形态）
```
# 旧：读者只看到黑盒调用，必须跳到 shared.py / verification.py / loaders.py
from scalim_misc.demo_big_data_report.shared import build_ecommerce_model
demand = build_ecommerce_model(cfg)            # ~300 行装配藏在库里
runtime_bindings = build_ecommerce_runtime_bindings()
verify_scalim_output(...)                       # ~900 行 oracle 藏在库里
```

### 目标形态（gold standard）
教程核心（loader / 派生计算函数 / DemandIr 装配 / Plan / Engine / 对拍断言）**逐 cell 写在 cells 内**，
并加一个 **"模型窥视" cell** 把装配产物（`demand.fields`、plan 元数据、runtime_bindings 键、targets）
直接渲染在 notebook 里，读者无需跳库。

## 改写模式（逐 cell 骨架）

一个 cells-native 章节 notebook 的模块级代码**只保留**：
- `import marimo`、`__generated_with`、`app = marimo.App(width="full")`
- （可选）`def run_chapter():` 薄适配层（`app.run()` → 提取 `chapter_result`）。
  registry 已内建同款投影，故 marimo 重存（editor 保存 / `marimo upgrade` 只保留 `@app.cell`）后对拍仍成立。

cells 内逐步骤展开（每步一个 cell，可就地修改重跑）：

| # | cell | 内容 | 原则 |
|---|---|---|---|
| 1 | 教学 intro | `mo.md` 主题、主线装配步骤、Gate 入口 | `hide_code=True` |
| 2 | marimo | `import marimo as mo` | — |
| 3 | 路径 | `ensure_repo_root_on_sys_path(__file__)` → return `repo_root` | 显式依赖保证 import 顺序 |
| 4 | 业务 imports | `scalim.*` API + 对拍辅助 | 允许 `scalim.*` 导入 |
| 5 | 用户侧代码 | 定义 loader / 派生计算函数 | **内联** |
| 6 | IR 装配 | `MainSourceIr`/`DemandIr`/`FieldIr`/`DerivedFieldIr`... | **内联** |
| 7 | **模型窥视** | 用 `mo.ui.table`/打印渲染 `demand.fields` 等装配产物 | **新增，防跳库** |
| 8 | 计划+接线 | `PlanBuilder`+`RuntimeBindings` | 内联 |
| 9 | 引擎运行 | `ScalimEngine(...)` + sink | 内联 |
| 10 | 期望 vs 实际 | 期望字面量直接写在 cells，`mo.ui.table` 对照 | 满足 r1114 |
| 11 | 断言+结果 | `make_chapter_result(passed, summary, details={..., "expected": ...})` | 见下方契约 |
| 12/13 | 展示 | `mo.callout` + `details_to_rows` 表格 | `hide_code=True` |

### 常见类型注意
- `demand.fields` 是 `mappingproxy`（键=field_id），遍历用 `demand.fields.values()`。
- `DerivedFieldIr` 可能没有 `source_id`，预览时用 `getattr(f, "source_id", "-")`。
- 保持 `run_chapter()`（chapter_id 为 `ch010_basics` 形态时用 `run_chapter()`；带 `run_<id>` 的形态别改坏 registry resolver，`chapters/registry.py` 的 `run_resolver` 决定）。

## 章节结果契约（必须满足）

- 末尾 cell 产出 `chapter_result`（至少 `{"passed", "summary", "details"}`）。
- `details` 若为 dict 字面量，**MUST 至少含一个 `expected` 前缀键**（r1114；`expected` 快照供 headless/pytest 定位）。
- 消费大的运行可加 `knob`/`run_button`，但默认值路径 MUST 确定性可对拍（r1112）。

## 可复用零件边界（r1111）

`scalim_misc` 只承载三类内容，其余一律 in-cell：

1. **loader 模块**（YAML `loader: "<module>:<fn>"` 必须是 importable 的模块级函数，marimo 只写 cells，故不能内联）：
   `scalim_misc/demo_big_data_report/{loaders,min_loaders,stage_perf_loaders}.py`、`examples/public_api/_fixtures.py`。
2. **对拍零件**（期望/断言/度量的机械面，无教学叙事）：`notebook_support/{chapter_result,counting_sink,rss_proxy,results_view,yaml_excerpt}.py`。
3. **runner/投影基础设施**：`notebook_support/{chapters_registry,pathing,cell_source}.py`、`examples/*`、`readme_*_gen.py`。

必须内联到 cells：Demand/Plan/RuntimeBindings/Engine 的构造与注入顺序、期望字面量、断言展开、`mo.*` 展示。

- 若某章节需完整电商模型（多源/多级 Join/派生），可保留 `build_ecommerce_model`/`build_ecommerce_runtime_bindings`
  作为**复杂复用零件**，但 MUST 用"模型窥视 cell"把其装配产物渲染出来，避免读者跳库。
- 应用场景轨（`chapters_of_scenarios/`，`ch210`–`ch260`）同样 in-cell；其 mock HTTP / YAML fixture 零件在
  `scalim_misc/demo_big_data_report/{scenario_fixtures,scenario_http_mock}.py`。

## 配套门禁与验证（改动后必跑，全绿才算完成）

仓库根目录执行：
```bash
# 1) 单章 headless 对拍（与 just examples 同源）
uv run python -c "
from notebooks.marimo.demo_big_data_report.chapters_of_ir.registry import run_selected_chapters
for r in run_selected_chapters(chapter_ids=['<chapter_id>']):
    print('PASS' if r.passed else 'FAIL', r.summary)
    if not r.passed: print(r.details)
"

# 2) cells-native 机械门禁（r1113 禁 run_* 委托 / r1114 期望键）
uv run python scripts/check-notebook-cells-native.py --check --quiet

# 3) 单元格式/lint
uv run ruff check <file> && uv run ruff format --check <file>

# 4) 集成测试
uv run pytest tests/integration/test_demo_big_data_report_chapters.py -q

# 5) 全量 examples gate（just qa 的一部分）
just examples
# 其实现就是 `scripts/run-marimo-notebooks.py`：自动发现 `demo_*`/`example_*` 套件 →
# 发现带 `registry.py` 的 `chapters*` 轨道 → 调 `run_all_chapters()` 跑对应 notebook 对拍。
# `notebooks/marimo/` 内因此不再放「非 marimo 的枢纽 .py」；只有 ch*.py 与 registry.py。
```

## 金标准参考

- **完全内联最小模型**：`notebooks/marimo/demo_big_data_report/chapters_of_ir/ch010_basics.py`
  （loader/DemandIr 装配/Engine/断言全在 cells；根 README 的 Python 代码块即其可见 cells 投影）。
- **最小 YAML 第一口**：`notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch005_yaml_dsl_min.py`
  （YAML SSOT：`declared_yaml_dsl/min_report.yaml`）。
- **同域内存对比**：`notebooks/marimo/demo_big_data_report/chapters_of_ir/ch020_memory_compare.py`
  （naive vs scalim；RSS 代理与计数 sink 零件在 `scalim_misc.notebook_support`）。
- **主教程复用复杂零件但带窥视**：改写后仍用 `build_ecommerce_model` 的章节应加窥视 cell。

## 常见坑（Gotchas）

- `app.run()` 创建全新 `__main__` 上下文，imports 必须写在 cells 内，不能依赖模块级 import。
- 不要手工编辑任何 `*.gen.*` 文件或 `BEGIN/END AUTOGEN` 区块；改 docs 用 `just gen-docs`。
- 与 `just check-notebooks-coverage` 相关：改动导入不影响覆盖统计，但别移除 `scalim.*` 公开面覆盖。
- 改完先跑 `ruff format`（140 行宽、双引号），再提交；纯重构走 `llman-sdd-quick`，不建 change 目录。
