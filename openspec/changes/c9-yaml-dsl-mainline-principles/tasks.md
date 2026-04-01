## 1. 主线原则落板

- [ ] 1.1 在 YAML DSL 相关主文档与变更索引中写清单主线原则: 不引入 `dsl_version`、不维护并行 parser/schema、`YAML = authoring`、`Python/CLI = runtime policy`、`KV-first`、workflow 不做 imports expansion; 文档 SSOT 为 `docs/doc/**`,若涉及注入区块使用 `just gen-docs` 刷新并以 `just qa` 验收漂移
- [ ] 1.2 清理旧总提案迁移后的残留引用与排序说明,确保活跃提案链路以 `c9 -> c10/c12/c13/c14/c15 -> c999` 为主; OpenSpec 工件以 `openspec/changes/**` 为 SSOT,通过 `just openspec-check` 验收

## 2. 审核护栏

- [ ] 2.1 为后续 YAML DSL 提案补一份统一的 review checklist / 原则说明,明确禁止重新引入并行 DSL 版本与 workflow imports expansion; 文档 SSOT 为 `docs/doc/**` 或相应 skill/docs SSOT,若有注入区块用 `just gen-docs` 刷新
- [ ] 2.2 运行 `just openspec-check` 确认 `c9` 及相关活跃 changes 的工件关系有效

## 3. 质量验收

- [ ] 3.1 运行 `openspec status --change c9-yaml-dsl-mainline-principles` 确认 `proposal/design/specs/tasks` 全部完成
