## Context

### Background

本 change 聚焦在一组“micro-tunes”: 即使不做完整语法重写,也能以较低实现成本显著降低当前 YAML DSL 的使用痛点。

这些 micro-tunes 来自对 `yaml-dsl-syntax-overhaul` 的 review 结论: 激进重写短期不推进,但其中一部分低风险改良可以先落地减痛,同时减少对 PyYAML anchors/alias 解析细节与对象身份的关键路径依赖,为未来可能的解析器升级/替换铺路。

### Constraints

- **Runtime**: `src/scalim/**` 运行时必须兼容 Python 3.6。
- **Docs governance**:
  - 任何包含 `.gen.` 的文件为生成物,禁止手改。
  - 任何 `<!-- BEGIN AUTOGEN:<id> -->` / `<!-- END AUTOGEN:<id> -->` 区块为受控注入区块,禁止手改区块内部。
  - 变更后需要运行 `just gen-docs` 刷新 docs-site 生成页与注入区块。
- **OpenSpec governance**: 共享/发布前必须通过 `just openspec-check`。
- **Breaking 策略**: 除非需求明确要求兼容,不保留旧写法兼容分支;仓内所有旧写法一次性升级到新写法。

### Canonical implementation pointers (today)

- JSON Schema: `src/scalim/dsl/by_yaml/schema/demand.gen.json` (由 `scripts/gen-yaml-dsl-schema.py` 生成)
- Semantic validator: `src/scalim/dsl/by_yaml/config_parsing/validator.py` + `validators/**`
- CLI entrypoints: `src/scalim/cli/yaml_dsl.py`
- Editor schema mirror: `frontend/scalim-yaml-dsl-editor/**/schema/demand.gen.json` (由 `just gen-yaml-dsl-editor-schema` 同步)

## Goals / Non-Goals

**Goals:**
- 让用户在不学习 YAML anchors/alias 细节的情况下完成常见写法: relation 引用、output 字段选择与 params runtime vars。
- 降低“概念命名误导”: 顶层派生字段入口清晰表达其语义边界。
- 统一 params 语言形态,提升 schema hover 与错误诊断的可解释性。
- 提升迁移/排错体验: field_id vs data_key 误用能给出可操作修复建议。
- 一步到位升级仓内所有示例/fixtures/docs/skills/frontend examples,不保留旧写法分支。

**Non-Goals:**
- 不做完整语法重写/不引入版本标签(v1/v2/v3)。
- 不改变 IR 语义边界(仅改变表达方式与校验/诊断)。
- 不实现 `fields` 的“跨多数据源/多需求字段入口”新能力(仅预留命名空间)。

## Decisions

### Decision 1: `fields` → `derived_fields` 一步到位迁移,不保留旧写法

`fields` 在当前 DSL 中只允许派生字段,与读者直觉强冲突。将其改名为 `derived_fields`,并将 `fields` 预留给未来扩展:

- 方案 A: 同时支持 `fields` 与 `derived_fields`(兼容) → 维护成本高,且阻碍 `fields` 被重用为“更通用入口”。
- **方案 B(选择)**: 直接改名并一次性升级仓内写法,对外通过升级指南/升级器承接迁移。

### Decision 2: runtime vars 统一为指令节点 `{$runtime: name}`,移除 `$runtime.name` 字符串占位符

目标是把 runtime vars 与 `$keys/$rows` 统一成同一种 AST 形态,便于 schema 表达与 hover 解释,也避免字符串模板解析的隐式规则:

- 方案 A: 继续同时支持 `$runtime.name`(兼容) → 增加维护面与诊断复杂度。
- **方案 B(选择)**: 统一到 `{$runtime: name}` 并在 validator 中对旧写法 fail-fast,提示升级路径。

### Decision 3: 引用优先提供稳定 string ref,anchors/alias 仅作为可选复用

对未来解析器升级/替换而言,anchors/alias 的对象身份与 merge 行为都可能成为兼容性风险点。因此:

- relation 引用新增 `relation: <relation_id>` string ref,并在语义 validator 中做存在性与 chain 校验。
- `output.fields` 新增 string sugar,让“最简单场景”不必写对象也不必使用 alias。
- 盘点当前 DSL 中其它依赖 alias 身份/解析细节的场景,优先为其补齐 string ref 兜底(若存在),避免未来升级解析器时出现不可控的兼容性问题。
- 仍允许用户在需要时使用 steps 对象/对象条目覆写,但仓内 canonical 示例应优先使用 string 形式。

### Decision 4: 文档/生成边界与 drift gate 收敛在实现前确定

本 change 涉及 schema/文档/skill/editor 的联动,必须在实现前明确哪些文件是 SSOT、哪些是生成物,并用 gate 防漂移:

- **SSOT**:
  - schema 生成脚本: `scripts/gen-yaml-dsl-schema.py` + `src/scalim/dsl/by_yaml/schema_dsl/**`
  - editor schema 同步脚本: `scripts/gen-yaml-dsl-editor-schema.py`
- **生成物(禁止手改)**:
  - `src/scalim/dsl/by_yaml/schema/demand.gen.json`
  - `frontend/scalim-yaml-dsl-editor/**/schema/demand.gen.json`
  - `docs/doc/**/*.gen.md` 与 injected blocks
- **Drift gates**:
  - `just gen` / `just qa` 覆盖 schema-drift 与 docs 治理检查
  - `just openspec-check` 覆盖 sanitize + OpenSpec validate

## Risks / Trade-offs

- [Breaking 变更影响下游配置] → 提供升级指南 + (可选)升级器脚本/CLI 子命令,并在错误信息中提示“怎么改”。
- [schema-only 与 full validate 行为不一致] → 对新增 union/sugar 做 schema/validator 双侧对齐,并补充 fixtures 覆盖。
- [output.fields string sugar 引入歧义] → 规定 `source.field_id` 仅用于消歧;遇到同名 field_id 必须显式 source。
- [runtime vars 指令化影响面广] → 在 params 校验处 fail-fast,给出最小迁移片段,并在升级文档中集中说明。

## Migration Plan

1) 实现语法与 validator/schema 更新,并补齐测试与 fixtures 覆盖
2) 一步到位升级仓内所有 YAML 示例/fixtures/skills/frontend examples
3) 新增升级指南: `docs/doc/yaml-dsl/upgrades/2026-03-12-yaml-dsl-micro-tunes.md`,并运行 `just gen-docs` 注入索引
4) 跑通门禁: `just gen` + `just qa` + `just openspec-check`

## Open Questions

- `output.fields` 的 `source.field_id` 是否允许更复杂的路径(例如包含更多 `.`)？本 change 默认仅支持单个 `.` 分隔的二段式。
- 是否需要提供“自动升级器”作为强制入口(例如 `PROJECT_CLI_NAME yaml-dsl upgrade`)？或先以升级指南 + 明确报错承接。
