# YAML DSL 升级指南

??? note "适用读者"
    - 需要把旧 YAML DSL 配置一次性升级到当前写法的使用方
    - 维护 YAML schema/validator/编辑器提示的贡献者

本目录按“变更批次”记录 YAML DSL 的 breaking changes、语义收敛点与迁移方式。

说明:

- 升级指南 SSOT 仅维护在 `agentdev/skills/scalim-yaml-dsl/references/upgrades/`。
- docs-site 不再生成升级页副本；本页仅提供到 SSOT 的链接索引(运行 `just gen-docs` 更新索引区块)。

升级清单:

<!-- BEGIN AUTOGEN:yaml-dsl-upgrades-index -->
- [2026-03-10: yaml-field-extract](#code=agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-10-yaml-field-extract.md)
- [2026-03-10: yaml-source-normalize](#code=agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-10-yaml-source-normalize.md)
- [2026-03-11: yaml-params-template](#code=agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-11-yaml-params-template.md)
- [2026-03-13: demand-dsl-breaking](#code=agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-13-demand-dsl-breaking.md)
- [2026-03-13: derived-outputs-set-aggregations](#code=agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-13-derived-outputs-set-aggregations.md)
- [2026-03-13: yaml-dsl-outputs](#code=agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-13-yaml-dsl-outputs.md)
- [2026-03-13: yaml-reuse-workflow](#code=agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-13-yaml-reuse-workflow.md)
- [2026-03-13: yaml-source-normalize-shapes](#code=agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-13-yaml-source-normalize-shapes.md)
- [2026-03-14: yaml-dsl-output-fields-alias](#code=agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-14-yaml-dsl-output-fields-alias.md)
- [2026-03-16: yaml-dsl-outputs-aggregate-fields](#code=agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-16-yaml-dsl-outputs-aggregate-fields.md)
- [2026-03-18: yaml-workflow-dag-ctx-resources](#code=agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-03-18-yaml-workflow-dag-ctx-resources.md)
- [2026-04-07: yaml-dsl-import-roots-registry](#code=agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-04-07-yaml-dsl-import-roots-registry.md)
- [2026-04-08: yaml-dsl-api-naming-alignment](#code=agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-04-08-yaml-dsl-api-naming-alignment.md)
- [2026-07-12: book-write-policy-python-ssot](#code=agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-07-12-book-write-policy-python-ssot.md)
- [2026-07-13: normalize-xlsx-book-ir-path-presence](#code=agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-07-13-normalize-xlsx-book-ir-path-presence.md)
- [2026-07-13: unified-xlsx-book-kind](#code=agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-07-13-unified-xlsx-book-kind.md)
<!-- END AUTOGEN:yaml-dsl-upgrades-index -->
