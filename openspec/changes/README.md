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

> 推荐处理顺序(Next):
> `yaml-dsl-extensions-schema` →
> `yaml-dsl-extensions-host-core` →
> `yaml-dsl-extensions-transformers` →
> `yaml-dsl-extensions-compute` →
> `yaml-dsl-extensions-output-format-registry` →
> `yaml-dsl-extensions-custom-aggregates` →
> `yaml-dsl-extensions-analyze-cli` →
> `prompt-eval-workflow`

1) YAML DSL extensions 系列（由 preproposal 拆分）
- 目标: 将 `extensions` 扩展方案按“底座 → 功能面”拆分为可实施的 changes,逐步落地并保持 `just qa` 可用。
- 当前实现入口(SSOT):
  - `openspec/changes/yaml-dsl-extensions-schema/`
  - `openspec/changes/yaml-dsl-extensions-host-core/`
  - `openspec/changes/yaml-dsl-extensions-transformers/`
  - `openspec/changes/yaml-dsl-extensions-compute/`
  - `openspec/changes/yaml-dsl-extensions-output-format-registry/`
  - `openspec/changes/yaml-dsl-extensions-custom-aggregates/`
  - `openspec/changes/yaml-dsl-extensions-analyze-cli/`
- Umbrella/reference: `openspec/changes/archive/2026-03-15-yaml-dsl-extensibility-preproposal/`（Review & Split 已完成,保留设计与全量 delta spec 作为参考）

2) `prompt-eval-workflow/`
- 目标: 建立确定性 prompt-eval core（先做静态/边界用例, 后续再扩展模型评测）。
- 当前状态见 `openspec/changes/prompt-eval-workflow/tasks.md`（当前为 DELAYED; 5.* 模型层需额外配置,暂不作为默认门禁）。

3) `c10-workflow-ir-roadmap/`
- 目标: 先确立 workflow 的 IR/节点系统作为统一底座,将 YAML 语法后置为“编译到 IR 的前端”,并为 dataset/ctx/输出节点/选择器等能力给出拆分与演进路线。
- 当前状态: proposal 待补齐;作为 roadmap change 推进。

4) `c20-workflow-dag-context-passing/`
- 目标: 将 workflow 从“并发批量执行 runs”扩展为更直觉的 DAG 编排,并提供 run 间 `ctx`/init_vars 传递能力(便于多阶段流水线与 scalim-viz 工作流视图)。
- 当前状态: **DELAYED**（proposal + 最小 delta spec 占位; 未进入设计/任务拆解）。

5) `c30-workflow-shared-output-containers/`
- 目标: 支持多 demand 合并到同一个最终 workbook/csv（多 demand 单/多 sheet），通过 workflow 统一管理共享输出容器资源与写出/追加语义。
- 当前状态: **DELAYED**（proposal + 最小 delta spec 占位; 未进入设计/任务拆解）。

## 已归档（索引）

- 完整列表见 `openspec/changes/archive/`。
- 近期归档（示例）:
  - `openspec/changes/archive/2026-03-15-yaml-dsl-extensibility-preproposal/`
  - `openspec/changes/archive/2026-03-15-frontend-yaml-dsl-editor-adaptations/`
  - `openspec/changes/archive/2026-03-15-scalim-viz-workflow-adaptations/`
  - `openspec/changes/archive/2026-03-15-marimo-notebooks-examples-suite/`
  - `openspec/changes/archive/2026-03-14-yaml-dsl-output-fields-alias/`
  - `openspec/changes/archive/2026-03-14-docs-demo-big-data-report-mainline/`
  - `openspec/changes/archive/2026-03-14-marimo-reexport-learning-suite/`
