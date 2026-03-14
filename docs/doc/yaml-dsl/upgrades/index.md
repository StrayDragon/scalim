# YAML DSL 升级指南

??? note "适用读者"
    - 需要把旧 YAML DSL 配置一次性升级到当前写法的使用方
    - 维护 YAML schema/validator/编辑器提示的贡献者

本目录按“变更批次”记录 YAML DSL 的 breaking changes、语义收敛点与迁移方式。

说明:

- 本目录下除 `index.md` 外的升级指南页由 SSOT 自动生成(文件名 `*.gen.md`); SSOT 在 `artifacts/skills/scalim-yaml-dsl/references/upgrades/`(运行 `just gen-docs` 更新)。

升级清单:

<!-- BEGIN AUTOGEN:yaml-dsl-upgrades-index -->
- [2026-03-10: yaml-field-extract](2026-03-10-yaml-field-extract.gen.md)
- [2026-03-10: yaml-source-normalize](2026-03-10-yaml-source-normalize.gen.md)
- [2026-03-11: yaml-params-template](2026-03-11-yaml-params-template.gen.md)
- [2026-03-13: demand-dsl-breaking](2026-03-13-demand-dsl-breaking.gen.md)
- [2026-03-13: derived-outputs-set-aggregations](2026-03-13-derived-outputs-set-aggregations.gen.md)
- [2026-03-13: yaml-dsl-outputs](2026-03-13-yaml-dsl-outputs.gen.md)
- [2026-03-13: yaml-reuse-workflow](2026-03-13-yaml-reuse-workflow.gen.md)
- [2026-03-13: yaml-source-normalize-shapes](2026-03-13-yaml-source-normalize-shapes.gen.md)
- [2026-03-14: yaml-dsl-output-fields-alias](2026-03-14-yaml-dsl-output-fields-alias.gen.md)
<!-- END AUTOGEN:yaml-dsl-upgrades-index -->
