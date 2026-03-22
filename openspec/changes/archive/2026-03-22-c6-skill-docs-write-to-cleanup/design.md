## Context

workflow YAML 的写入 authoring surface 已以 `workflow.runs[*].writes`（list of intents）作为唯一真相,且 runtime 已移除 `write_to`.

但在 `scalim-yaml-dsl` skill 的 references 与部分 OpenSpec 文档中,仍残留把 `write_to` 当作当前语法的表述,并被生成器汇总进 `references/syntax-catalog.gen.md` 等生成物中,造成作者误导.

本变更以“文档/生成物必须与 canonical schema 一致”为准绳,清理这些残留并补齐回归门禁.

## Goals / Non-Goals

**Goals:**
- `references/syntax-catalog.gen.md` 不再出现 `write_to.sheetbook_*` 等旧字段表述
- `scalim-yaml-dsl` skill 的 workflow 引导文案不再宣传 `write_to` 作为当前写法
- 通过测试/漂移门禁确保后续不会回归

**Non-Goals:**
- 不改动 workflow runtime/schema/IR（不引入 `write_to` 兼容层）
- 不在本变更内系统性清理所有 repo 中的历史记录（仅清理会误导作者的 surface 文案）

## Decisions

- D1. `src/scalim/dsl/by_yaml/schema/workflow.gen.json` 是 workflow YAML 的唯一真相；文档与生成物不得宣传已移除字段.
- D2. 对仍需提及 `write_to` 的情况,仅允许出现在“迁移/历史”上下文中,并明确其已被移除与替代写法.
- D3. 生成物禁止手改：所有 `.gen.md` 与注入区块必须通过 `just gen-agent-skill` / `just gen-docs` 刷新.

## Risks / Trade-offs

- [风险] 历史 upgrade 文档被其它内容引用,改动可能影响检索 → [缓解] 保留文件名不变,只修正文案与示例为当前写法,并在必要处补迁移提示.
- [风险] 将来若再次引入类似字段名,回归断言可能过严 → [缓解] 将断言限定在“语法索引/作者指引”范围,不要求全仓库无该字符串.
