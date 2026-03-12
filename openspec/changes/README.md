# OpenSpec Changes: 分组实施计划

本目录用于承载**未归档**的 change（proposal/design/spec/tasks）。我们按“组”推进实现：一组可能对应一个 change，也可能把多个强耦合 change 合并落地，以避免语义漂移与反复迁移成本。

## 全局约束（每组都必须满足）

1) **Breaking 一步到位**
- 除非需求明确要求兼容，否则不保留旧写法兼容分支；仓内所有旧写法一次性升级（YAML 示例/fixtures/notebooks/skills/frontend examples 等）。

2) **每组必须更新 canonical demo**
- 必须改造 `notebooks/marimo/examples/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`，确保新语义在可运行的真实配置里被覆盖。

3) **每组必须做下游适配盘点（脱敏规则）**
- 允许读取 `.tmp/known-outer-paths-using-this-package.txt` 用于盘点下游适配与同步修改。
- 输出/文档/规范中**不得引用其内容**（只能引用该文件路径本身）。

4) **每组必须交付“升级指南”，并接入自动索引**
- 在 `docs/doc/yaml-dsl/upgrades/` 新增一篇升级文档（文件名建议 `YYYY-MM-DD-<group>.md`）。
- 文档中用反引号写出：
  - 对应归档目录：`openspec/changes/archive/YYYY-MM-DD-<change>/`
  - 对应主规范：`openspec/specs/<spec>/spec.md`
- 跑 `just gen` 让 `artifacts/skills/scalim-yaml-dsl/references/task-upgrade-legacy.md` 自动注入升级索引（避免手工维护）。

5) **验收与归档流程**
- 每组完成后必须跑通：
  - `just gen`
  - `just qa`（包含前端构建检查）
- 然后将该组涉及的 change 归档到 `openspec/changes/archive/YYYY-MM-DD-.../`，等待 review。

## 已完成

- `yaml-field-extract` 已归档：`openspec/changes/archive/2026-03-10-yaml-field-extract/`
- `yaml-source-normalize` 已归档：`openspec/changes/archive/2026-03-10-yaml-source-normalize/`
- `yaml-inline-dynamic-params` 已归档：`openspec/changes/archive/2026-03-11-yaml-inline-dynamic-params/`
- `yaml-loader-params-template` 已归档：`openspec/changes/archive/2026-03-11-yaml-loader-params-template/`
- `add-derived-outputs` 已归档：`openspec/changes/archive/2026-03-11-add-derived-outputs/`
- `yaml-relative-import-paths` 已归档：`openspec/changes/archive/2026-03-11-yaml-relative-import-paths/`
- `doc-system-workflow` 已归档：`openspec/changes/archive/2026-03-12-doc-system-workflow/`
- `qa-hardening` 已归档：`openspec/changes/archive/2026-03-12-qa-hardening/`

## 待实现分组（按推荐顺序）

1) **Group: demand DSL 语法收敛（breaking）**
- `yaml-dsl-micro-tunes`

2) **Group: YAML 复用与编排（共享路径解析能力）**
- `yaml-dsl-imports`（建议先落地 `path_aliases`/import 展开）
- `yaml-dsl-workflow`（复用 `path_aliases`，实现 runs 编排 + shared preload cache）

3) **Group: 派生聚合 set 口径原语（为 ET 去状态壳打底）**
- `derived-outputs-set-aggregations`

4) **Group: 工具链侧改良（不阻塞主线）**
- `prompt-eval-workflow`
