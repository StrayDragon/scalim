# OpenSpec Changes

本目录承载 active changes（未归档变更）。目录名采用 `c<priority>-<name>` 形式,自然表达推进顺序（priority 越小越优先）。

不再维护“当前 changes 列表/推荐合并顺序”等人工索引；请直接按目录名排序查看。

## YAML DSL 主线原则(摘要)

当你在 `openspec/changes/` 下创建/评审 YAML DSL 相关变更时,默认遵循这些上位原则(完整 SSOT 以 `openspec/specs/yaml-dsl-mainline-principles/spec.md` 为准):

- 单主线原地演进: 不引入 `dsl_version`、不维护并行 parser/validator/schema
- `YAML = authoring`, `Python/CLI = runtime policy`
- KV-first: 需要稳定 ID/引用/复用的结构优先 mapping
- workflow 小而声明式,并拒绝 workflow imports expansion

约定:
- 归档目录: `openspec/changes/archive/`
- 在提案/文档中引用其它 change 时,只写 `<name>`（不带 `c<priority>-` 前缀）,避免优先级调整导致跨文档引用漂移
