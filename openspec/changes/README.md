# OpenSpec Changes: 工作区与归档

本目录用于承载**未归档**的 change（proposal/design/spec/tasks）。

- 工作区（未归档）: `openspec/changes/<change>/`
- 归档区（已完成）: `openspec/changes/archive/YYYY-MM-DD-<change>/`

> 说明: change 目录下的 `specs/` 为“delta spec”（只描述本 change 引入/修改的规范片段）；实现完成后会同步回 `openspec/specs/`。

## 约束（SSOT）

### A) 语义/接口类 change（YAML DSL / CLI / runtime 行为）

1) **Breaking 一步到位**
- 除非需求明确要求兼容，否则不保留旧写法兼容分支；仓内所有旧写法一次性升级（YAML 示例/fixtures/notebooks/skills/frontend examples 等）。

2) **覆盖 canonical demo**
- 只要 change 会影响 YAML authoring surface/语义，就必须更新并回归：
  - `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`

3) **下游适配盘点（脱敏规则）**
- 允许读取 `.tmp/known-outer-paths-using-this-package.txt` 用于盘点下游适配与同步修改。
- 输出/文档/规范中**不得引用其内容**（只能引用该文件路径本身）。

4) **升级指南 + 自动索引**
- 若 change 引入 breaking/migration，需要在 `artifacts/skills/scalim-yaml-dsl/references/upgrades/` 新增一篇升级文档（文件名建议 `YYYY-MM-DD-<group>.md`）。
- 跑 `just gen`/`just gen-docs` 让 docs-site 与 skill references 的索引自动更新（避免手工维护）。
- 升级文档中用反引号写出：
  - 对应归档目录：`openspec/changes/archive/YYYY-MM-DD-<change>/`
  - 对应主规范：`openspec/specs/<spec>/spec.md`

5) **验收与归档**
- 归档前必须跑通：
  - `just gen`
  - `just qa`
  - `just openspec-check`
- 完成后将 change 目录移动到 `openspec/changes/archive/YYYY-MM-DD-.../`。

### B) 工具链/文档类 change

- 仍需通过 `just qa` / `just openspec-check`；是否需要升级指南、canonical demo 覆盖按实际影响决定。

## 当前未归档 changes

1) `frontend-yaml-dsl-editor-adaptations/`
- 目标: 让编辑器模板/outline/visual 与最新 schema/validate 语义一致。
- 当前状态见 `openspec/changes/frontend-yaml-dsl-editor-adaptations/tasks.md`（当前为“进行中”; 剩余 5.2/5.6 需处理与归档）。

2) `prompt-eval-workflow/`
- 目标: 建立确定性 prompt-eval core（先做静态/边界用例, 后续再扩展模型评测）。
- 当前状态见 `openspec/changes/prompt-eval-workflow/tasks.md`（当前为 DELAYED; 5.* 模型层需额外配置,暂不作为默认门禁）。

3) `yaml-dsl-extensibility-preproposal/`
- 目标: pre-proposal：YAML-first extensibility surfaces（trusted YAML + Python extensions），用于评审并拆分后续可实施的 changes。
- 当前状态见 `openspec/changes/yaml-dsl-extensibility-preproposal/tasks.md`（优先 Review & Split）。

## 已归档（索引）

- 完整列表见 `openspec/changes/archive/`。
- 近期归档（示例）:
  - `openspec/changes/archive/2026-03-15-scalim-viz-workflow-adaptations/`
  - `openspec/changes/archive/2026-03-15-marimo-notebooks-examples-suite/`
  - `openspec/changes/archive/2026-03-14-yaml-dsl-output-fields-alias/`
  - `openspec/changes/archive/2026-03-14-docs-demo-big-data-report-mainline/`
  - `openspec/changes/archive/2026-03-14-marimo-reexport-learning-suite/`
