# notebooks/ 与示例回归体系全量分析：结构、覆盖面、SSOT 与可删性

本页只讲“真值依赖面”：`notebooks/` 不在 runtime 主链路里，但它**被门禁/脚本/测试/技能生成**当作 SSOT 引用。删它的难点不是删目录本身，而是要先处理 SSOT 迁移与 gate 拆分。

当前 `notebooks/` 体量很小(`du -sh notebooks` 约 144K)，但它的“引用半径”很大。

---

## 1) notebooks 的角色拆分：UI 与 runner 是两层

`notebooks/marimo/` 实际包含两类东西：

1) **marimo UI**(交互讲解)：例如 `notebooks/marimo/demo_big_data_report/demo_main.py`、`notebooks/marimo/example_public_api/index.py`
2) **headless runner**(回归门禁)：`notebooks/marimo/run_examples.py`

`just examples` 的入口就是 runner：

- `justfile: examples` → `python notebooks/marimo/run_examples.py`
- `just qa` 默认包含 `examples`

runner 做的事(事实)：

- 运行 `demo_big_data_report`：`scalim_misc.demo_big_data_report.chapters.registry::run_all_chapters`
- 运行 `example_public_api`：`scalim_misc.examples.harness::run_public_api_examples`

> 结论：如果你只是不想维护 marimo UI，你可以删除 UI 但保留 runner；反之，如果你想彻底精简回归套件，就要把 runner 从门禁拆掉并补上替代覆盖。

---

## 2) `packages/scalim-misc/`：notebooks 的真正 SSOT 实现层

notebooks 大量逻辑并不在 notebooks 本身，而在：

- `packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/`：按章节组织的可运行函数
- `packages/scalim-misc/src/scalim_misc/examples/public_api/`：稳定入口模块(`scalim.dsl.by_yaml` 等)的示例/回归实现
- `packages/scalim-misc/src/scalim_misc/examples/harness.py`：统一运行、汇总 PASS/FAIL、错误摘要

更关键的是：仓库多个生成脚本也依赖 `scalim-misc`：

- `scripts/gen-docs.py` 直接 import `scalim_misc.markdown_inject`(文档注入工具)
- `scripts/gen-agent-skill.py` 直接 import `scalim_misc.agent_skill_gen`(技能生成)

> 结论：如果你的“精简”目标包含删掉 `packages/scalim-misc/`，那不是删示例那么简单，而是要迁移脚本能力(至少 doc 注入与 skill 生成)到其它位置。

---

## 3) canonical YAML(当前 SSOT)是“全仓库引用中心”

当前多个入口把下面文件当作“唯一完整示例”(SSOT)：

- `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`

被引用的位置(部分关键点)：

- `scripts/gen-agent-skill.py`(注释中写明唯一完整示例来自该路径)
- `scripts/gen-viz-data.py` / `scripts/gen-viz-schedule-plan.py` 默认参数 `--yaml-path` 指向该文件
- tests：
  - `tests/test_yaml_dsl_output_fields_alias.py`
  - `tests/test_ecommerce_yaml_relation_field_id.py`
  - `tests/bench/test_bench_examples.py`(bench)
  - `tests/test_notebook_examples_readme_paths.py`(存在性约束)
- docs：
  - `docs/doc/getting-started/demo-big-data-report.md`
- artifacts：
  - `artifacts/skills/scalim-yaml-dsl.build-manifest.json` 中包含该文件路径(生成产物清单)

因此，“删 notebooks”若不先迁移 canonical YAML，会导致：

- skill 生成器失效或生成不完整
- viz 示例数据生成脚本默认路径失效
- 多个测试直接失败
- 文档引用断链

---

## 4) 覆盖报告(SSOT, generated)：`notebooks/marimo/marimo_coverage.gen.md`

该文件用于把 “notebooks 示例套件” 映射到可执行回归入口，避免示例碎片化，并为 CI 提供可检查的 drift 守护。

它由脚本生成，不手工维护：

- 生成脚本：`scripts/gen-marimo-coverage.py`
- 生成：`just gen-marimo-coverage`
- 漂移检查：`just marimo-coverage-drift-check`（已纳入 `just qa`）

覆盖口径(事实)：

- marimo hubs / chapters / canonical YAML fixtures
- `packages/scalim-misc` 中的 SSOT(章节/示例实现)
- headless runner：`notebooks/marimo/run_examples.py`
- pytest 复用点(如存在)

---

## 5) 可删性分级建议(按“删的收益/风险”排序)

### Level 1：只删 marimo UI，保留 runner 与 canonical YAML

适合：你不想维护交互笔记，但仍想保留 `just examples` 的回归价值。

动作：

- 删除/冻结 `notebooks/marimo/**/index.py`、`demo_main.py` 等 UI 文件
- 保留：
  - `notebooks/marimo/run_examples.py`
  - `notebooks/marimo/demo_big_data_report/by_yaml_dsl/*.yaml`(SSOT)
- 文档更新：把“交互教程入口”从 marimo 改为 “headless runner + docs 页面”

影响：

- `just notebook` 失效(需要从 `justfile` 移除)
- `just examples` 仍可保留

### Level 2：保留示例/回归，但迁移 SSOT 到 `examples/` 并删除 notebooks 整体

适合：你想删掉 `notebooks/` 目录，但仍希望保留 demo YAML 与回归 runner。

动作(最小迁移思路)：

1) 新建目录，例如：

- `examples/yaml/ecommerce_report.yaml`
- `examples/yaml/workflow_fixture.yaml`
- `examples/yaml/ecommerce_report_fragments.yaml`

2) 全仓库替换引用点：

- `scripts/gen-agent-skill.py` 的“唯一完整示例路径”
- `scripts/gen-viz-data.py` / `scripts/gen-viz-schedule-plan.py` 的默认 `--yaml-path`
- `tests/*` 中的 YAML 路径引用
- `docs/doc/getting-started/demo-big-data-report.md` 等文档
- `tests/test_notebook_examples_readme_paths.py` 需要重写为新目录约束

3) 把 `notebooks/marimo/run_examples.py` 的 runner 迁移为 `examples/run_examples.py`(或留在 `scripts/`)，并更新 `justfile: examples` 入口。

影响：

- marimo 依赖可从 dev group 移除(如果不再需要交互 UI)
- `just examples` 仍可保留(但入口换位置)

### Level 3：彻底移除示例回归(`just examples`)并用 pytest 替代覆盖

适合：你想把 repo 变成“纯库 + 测试 + 规范”，不维护大 demo。

动作：

- `justfile` 中 `check:` recipe 不再依赖 `examples`
- 删除 `packages/scalim-misc/src/scalim_misc/demo_big_data_report` 与 `examples/public_api` 套件(或外置)
- 在 `tests/` 中补齐你认为不可失去的覆盖点(建议直接参考 `notebooks/marimo/marimo_coverage.gen.md` 逐项落到测试)

风险：

- 需要你对“最小不可删能力”有明确清单，否则容易在后续演进中丢失端到端回归信号。
