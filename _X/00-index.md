# Scalim 全能分析报告索引(用于精简决策)

本目录的内容面向“删目录/拆仓/降低维护成本”的决策与落地。分析基于当前仓库真实代码与门禁入口(例如 `just qa`)，并尽量把每条结论落到**具体路径/符号/命令**上，便于你后续搬运到正式文档。

## 你最关心的两类精简

1) `frontend/`：两套 Svelte 工具(可视化回放 + YAML DSL 编辑器)，对**运行时库分发**不是必需，但会影响 `just qa`、文档与若干生成/漂移检查脚本。

2) `notebooks/`：`marimo` 交互教程 + “示例回归套件”(也是 `just qa` 的一部分)。其下的 canonical YAML(例如 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`)被多个脚本/测试/技能生成器当作 SSOT 引用，删之前必须先“迁移 SSOT”或同步改引用点。

## 报告分卷

- `01-capabilities.md`：框架能力全景图(按用户入口/语义边界/核心模块拆分)，每项能力给出实现位置与最小代码推演。
- `02-core-walkthrough.md`：从 YAML/Python 到 IR → Plan → Execution 的端到端真值推演(关键优先级、默认值与安全边界)。
- `03-frontends.md`：`frontend/scalim-viz` 与 `frontend/scalim-yaml-dsl-editor` 的能力、依赖面、与删除影响。
- `04-notebooks-and-examples.md`：`notebooks/marimo` 与 `packages/scalim-misc` 示例/回归的结构、覆盖面、与删除/迁移方案。
- `05-slimming-impact-matrix.md`：可删项影响矩阵(删什么、坏哪里、最小修复/替代方案)。
- `06-slimming-roadmap.md`：建议的分阶段精简路线(先解耦门禁/SSOT，再删目录；每阶段验证点与回滚点)。
- `07-marimo-demo_big_data_report-notebook-reorg.md`：基于“文档 + canonical YAML + 章节实现”的功能点扫描，并给出 `demo_big_data_report` 的 Marimo Notebook 章节化重组方案与 shared 下沉建议(处于 explore，不直接落地实现)。

## 术语约定(避免误会)

- **运行时代码**：`src/scalim/`，该目录要求保持 Python 3.6 兼容(见仓库 `AGENTS.md`)。
- **库分发边界**：`just dist-check` 的约束明确指出 wheel/sdist **不应包含** `tests/docs/notebooks/frontend/artifacts`；因此删除这些目录一般不会改变 PyPI 分发产物，但会影响研发体验与回归门禁。
- **SSOT**：当前仓库存在“单一真相”入口的约定(例如 canonical YAML、生成物与 injected blocks)。删除 SSOT 文件通常不是“删目录”这么简单，而是要先把 SSOT 迁移到新位置并更新所有引用点。
