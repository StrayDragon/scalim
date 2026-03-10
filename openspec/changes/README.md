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

## 已完成（示例）

- `yaml-field-extract` 已归档：`openspec/changes/archive/2026-03-10-yaml-field-extract/`

## 待实现分组（按推荐顺序）

### Group 1: Params 模板收敛（合并实现）

涉及 changes:
- `openspec/changes/yaml-inline-dynamic-params/`
- `openspec/changes/yaml-loader-params-template/`

目标（高层验收点）:
- `main_source.params` 与 `sources.*.params` 统一编译为共享的 params template IR（避免 preload/ref-load 两套语义）。
- 支持模板指令 `$keys` / `$rows`（nested 注入、composite key、稳定顺序与缓存语义）。
- 支持 `runtime_vars` 注入与 `$runtime.<name>` 占位符替换；缺失 runtime var fail-fast（报到具体配置路径）。
- `preload_forever` 的 params 透传语义收敛：仅当 `sources.<id>.params` **非空**才传 kwargs；为空保持零参 preload。
- 移除旧写法 `bind/to_bind`：validator fail-fast，并给出可直接照抄的替换建议片段（降低迁移摩擦）。

本组必须覆盖的 repo 改造:
- `notebooks/marimo/examples/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`：
  - 移除旧 bind/to_bind 写法，迁移为 `sources.*.params` 的 `$keys/$rows` 模板指令
  - 至少覆盖一个 `preload_forever + sources.<id>.params` 非空的示例
  - 至少覆盖一个 `$runtime.*` 注入的示例
- 下游适配盘点：读取 `.tmp/known-outer-paths-using-this-package.txt` 并同步升级关联代码（输出不得引用其内容）。

归档策略:
- 同一批次完成后同时归档两条 change（同一天日期）：
  - `openspec/changes/archive/YYYY-MM-DD-yaml-inline-dynamic-params/`
  - `openspec/changes/archive/YYYY-MM-DD-yaml-loader-params-template/`

### Group 2: Source Normalize（list→mapping 等结果形状收敛）

涉及 changes:
- `openspec/changes/yaml-source-normalize/`

目标（高层验收点）:
- 为 `sources.*` 增加 `normalize` 配置（显式拒绝 `main_source.normalize`）。
- 支持 `normalize.kind=index_by_key`：
  - 必填 `key_field`
  - `on_conflict` 默认 `error`（重复 key 运行时直接 fail-fast）；`first/last` 需显式声明
- normalize 在执行期应用于“whole-result”，并与 `preload_forever` 缓存路径保持一致的结果形状与观测。

本组必须覆盖的 repo 改造:
- `notebooks/marimo/examples/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`：
  - 至少引入一个真实 `normalize.kind=index_by_key` 的场景（例如 lookup loader 返回 list，靠 normalize 归一化成 mapping）
- 下游适配盘点：读取 `.tmp/known-outer-paths-using-this-package.txt` 并同步升级关联代码（输出不得引用其内容）。

归档策略:
- 完成后归档：`openspec/changes/archive/YYYY-MM-DD-yaml-source-normalize/`

### Backlog: add-derived-outputs（暂缓/搁置）

涉及 changes:
- `openspec/changes/add-derived-outputs/`

状态:
- 需求侧场景与默认策略未对齐前不推进实现；避免过早增加 YAML DSL 复杂度。

