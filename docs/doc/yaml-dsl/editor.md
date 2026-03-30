# 配置补全与编辑体验

??? note "适用读者"
    - 写 YAML 配置并希望获得补全/校验的使用方
    - 需要更严格语义校验的开发者

??? note "现状"
    - 仓库内的 Web 编辑器 `frontend/scalim-yaml-dsl-editor/` 已移除(后续计划以 LSP/IDE 集成为主)
    - 当前推荐路径: JSON Schema 补全/校验 + `scalim-cli` 做语义校验

## Schema 补全/校验

YAML DSL 的 canonical schema 生成物在:

- `src/scalim/dsl/by_yaml/schema/demand.gen.json`
- `src/scalim/dsl/by_yaml/schema/workflow.gen.json`

刷新生成物:

```bash
just gen-yaml-dsl-schema
```

在 YAML 文件头使用 IntelliJ 兼容的 schema header(推荐):

```yaml
# $schema: /ABS/PATH/TO/src/scalim/dsl/by_yaml/schema/workflow.gen.json
```

## 语义校验(命令行)

需要对齐运行时的更严格语义约束时,使用 CLI 校验:

```bash
scalim-cli yaml-dsl validate /path/to/config.yaml
```

## LSP/IDE 集成(规划)

后续方向会以 LSP/IDE 插件替代仓库内 Web 编辑器; 设计讨论见:

- `openspec/notplan-changes/c999-yaml-dsl-lsp/proposal.md`
- `openspec/notplan-changes/c999-yaml-dsl-lsp/design.md`
