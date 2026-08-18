# YAML DSL 升级指南

??? note "适用读者"
    - 需要把旧 YAML DSL 配置一次性升级到当前写法的使用方
    - 维护 YAML schema/validator/编辑器提示的贡献者

本目录按“变更批次”记录 YAML DSL 的 breaking changes、语义收敛点与迁移方式。

说明:

- 升级指南 SSOT 仅维护在 `agentdev/skills/scalim-yaml-dsl/references/upgrades/`。
- docs-site 不再生成升级页副本；本页仅提供到 SSOT 的链接索引(运行 `just gen-docs` 更新索引区块)。
- **非 breaking 的版本亮点**（如 0.10 默认性能行为 / opt-in）不在本索引：见 [版本亮点](../../releases/index.md) / [0.10.0 重点特性](../../releases/0.10.0/)。

升级清单:

<!-- BEGIN AUTOGEN:yaml-dsl-upgrades-index -->
- [2026-03-10: yaml-field-extract](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-10-yaml-field-extract.md?ref)
- [2026-03-10: yaml-source-normalize](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-10-yaml-source-normalize.md?ref)
- [2026-03-11: yaml-params-template](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-11-yaml-params-template.md?ref)
- [2026-03-13: demand-dsl-breaking](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-13-demand-dsl-breaking.md?ref)
- [2026-03-13: derived-outputs-set-aggregations](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-13-derived-outputs-set-aggregations.md?ref)
- [2026-03-13: yaml-dsl-outputs](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-13-yaml-dsl-outputs.md?ref)
- [2026-03-13: yaml-reuse-workflow](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-13-yaml-reuse-workflow.md?ref)
- [2026-03-13: yaml-source-normalize-shapes](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-13-yaml-source-normalize-shapes.md?ref)
- [2026-03-14: yaml-dsl-output-fields-alias](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-14-yaml-dsl-output-fields-alias.md?ref)
- [2026-03-16: yaml-dsl-outputs-aggregate-fields](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-16-yaml-dsl-outputs-aggregate-fields.md?ref)
- [2026-03-18: yaml-workflow-dag-ctx-resources](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-18-yaml-workflow-dag-ctx-resources.md?ref)
- [2026-04-07: yaml-dsl-import-roots-registry](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-04-07-yaml-dsl-import-roots-registry.md?ref)
- [2026-04-08: yaml-dsl-api-naming-alignment](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-04-08-yaml-dsl-api-naming-alignment.md?ref)
- [2026-07-12: book-write-policy-python-ssot](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-07-12-book-write-policy-python-ssot.md?ref)
- [2026-07-13: normalize-xlsx-book-ir-path-presence](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-07-13-normalize-xlsx-book-ir-path-presence.md?ref)
- [2026-07-13: unified-xlsx-book-kind](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-07-13-unified-xlsx-book-kind.md?ref)
- [2026-07-18 — `ISink.discard` 显式失败清理合约](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-07-18-sink-discard-explicit-contract.md?ref)
- [2026-07-18 — tabular bus object + sink accept / opt-in precheck](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-07-18-tabular-bus-object-sink-accept-precheck.md?ref)
- [2026-07-20: remove-deprecated-xlsx-file-memory-kinds](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-07-20-remove-deprecated-xlsx-file-memory-kinds.md?ref)
- [2026-07-24: remove-derived-outputs-cardinality-guardrails](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-07-24-remove-derived-outputs-cardinality-guardrails.md?ref)
- [2026-07-24: remove-score-by-rank-builtin](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-07-24-remove-score-by-rank-builtin.md?ref)
- [2026-07-28: remove-book-budget-policy](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-07-28-remove-book-budget-policy.md?ref)
- [2026-07-28: remove-dedup-and-two-stage-derived](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-07-28-remove-dedup-and-two-stage-derived.md?ref)
- [2026-08-09 — YAML `lookup_chunk_size` → Python `LookupChunking`（c40）](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-08-09-lookup-chunking-python-ssot.md?ref)
- [Upgrade: OutputWriteLayout（Python 写出布局 SSOT）](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-08-11-output-write-layout.md?ref)
- [2026-08-18 — 图边存 `source_id`，策略只住目录（c50）](repo:agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-08-18-source-id-graph-refs.md?ref)
<!-- END AUTOGEN:yaml-dsl-upgrades-index -->
