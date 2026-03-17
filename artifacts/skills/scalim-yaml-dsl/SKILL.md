---
name: scalim-yaml-dsl
description: "编写、重构、升级、校验和排错 Scalim YAML DSL 配置,并为旧报表脚本规划渐进迁移到 YAML DSL 的方案。适用于 `scalim dsl`、`scalim yaml dsl`、YAML LSP/schema 配置、修复 `yaml-dsl validate` / `schema validate` 报错、以及判断哪些逻辑应留在 Python 与哪些应下沉到 YAML 的场景。"
---

# Scalim YAML DSL

先识别任务类型,只读取最少的 reference:

- 新写或改写 YAML: 读 [references/task-authoring.md](references/task-authoring.md)
- 旧写法直接升级到当前结构: 读 [references/task-upgrade-legacy.md](references/task-upgrade-legacy.md)
- 校验、订正、排错: 读 [references/task-validate-debug.md](references/task-validate-debug.md)
- 旧报表脚本渐进迁移方案: 读 [references/task-report-migration-playbook.md](references/task-report-migration-playbook.md)
- 下游适配盘点与同步: 读 [references/task-downstream-adaptation.md](references/task-downstream-adaptation.md)
- 需要按批次快速定位 breaking/migration: 读 [references/generated/yaml-dsl-upgrades.gen.md](references/generated/yaml-dsl-upgrades.gen.md)
- 需要阅读完整升级指南(SSOT): 读 `references/upgrades/*.md`
- 需要全量语法/API: 读 [references/syntax-catalog.gen.md](references/syntax-catalog.gen.md) 和 [references/generated/cli-lsp-reference.gen.md](references/generated/cli-lsp-reference.gen.md)
- 需要完整 canonical example: 读 [references/generated/example-full/ecommerce_report.gen.yaml](references/generated/example-full/ecommerce_report.gen.yaml)

先给出最小可执行命令,再开始分析或改 YAML:

- 仓库内完整校验: `uv run scalim-cli yaml-dsl validate <file.yaml>`
- 仓库内 schema 校验: `uv run scalim-cli yaml-dsl schema validate <file.yaml>`
- 仓库外完整校验: `uvx --from "scalim[cli]" scalim-cli yaml-dsl validate <file.yaml>`
- 仓库外 schema 校验: `uvx --from "scalim[cli]" scalim-cli yaml-dsl schema validate <file.yaml>`
- 仓库内查询 schema 绝对路径: `uv run scalim-cli yaml-dsl schema path`
- 仓库外查询 schema 绝对路径: `uvx --from "scalim[cli]" scalim-cli yaml-dsl schema path`

完整 canonical example 故意不带头部(也就是 schema modeline)。本地编辑时,我们一般用下面这套“团队通用”的做法(先开 schema server,再批量写入头部):

- 启动本机 schema server(默认 `--host 0.0.0.0 --port 62831`): `uv run scalim-cli yaml-dsl schema-serve`
- 批量插入/更新头部(统一写 IntelliJ 兼容 modeline,并会识别/升级 legacy `yaml-language-server` 头): `uv run scalim-cli yaml-dsl upsert-lsp-comment --type demand --schema-path http://localhost:62831 <paths...>`

```yaml
# $schema: http://localhost:62831/demand.gen.json
```

工作时遵守这些硬规则:

- 顶层 `fields` 只放派生字段,必须使用 `compute` 或 `call_by`
- `main_source.fields` / `sources.<id>.fields` 只放源字段,不要把派生逻辑塞进去
- `relations.*.steps.from/to` 写 YAML 的字段 ID(不要写 loader 的 `data_key`)
- 不要硬记/猜语法: 以 schema / 生成文档为准(需要时看 `references/syntax-catalog.gen.md`、`references/generated/cli-lsp-reference.gen.md`、`references/generated/example-full/ecommerce_report.gen.yaml`)
- 迁移/升级优先看自动索引的 upgrades(从 `references/task-upgrade-legacy.md` 进入,或读取生成的 upgrades 摘要)
- 未明确要求兼容时,旧 DSL 写法直接升级到当前结构,不要保留兼容层
- 交付时必须说明: 跑了哪些校验,缺了哪些依赖,哪些内容仍未在真实环境验证

只在需要时再读大 reference,不要默认把全量 catalog 和 playbook 一起塞进上下文。
