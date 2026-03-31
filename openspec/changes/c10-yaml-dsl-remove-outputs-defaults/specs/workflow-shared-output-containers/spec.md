## MODIFIED Requirements

### Requirement: workflow YAML exposes a stable authoring surface for shared resources and write intents
系统 MUST 为共享输出容器提供可实现、可校验的 workflow YAML authoring surface,并将“写入意图”从 workflow `writes` 收敛为 demand outputs 的 IO 绑定(由 workflow 编译期推导写入节点):

- 资源声明:
  - `workflow.resources.books.<book_id>` MUST 为 mapping 且 MUST 满足 `yaml-dsl-books-resources` 对 book 的约束
- 写入意图:
  - workflow YAML MUST NOT 再暴露已移除的 workflow-level 写入 intents authoring surface
  - 系统 MUST 从每个 run 引用的 demand YAML 中读取 `outputs[*].to` / `outputs[*].write` 推导等价的写入节点集合

迁移约束(破坏性变更):

- legacy workflow resource groups(workbooks/csvs/sheetbooks) MUST 被拒绝并给出迁移提示(迁移到 `workflow.resources.books`)
- 已移除的 workflow-level 写入 intents MUST 被拒绝并给出迁移提示(迁移到 demand outputs 的 `to/write` 绑定)

#### Scenario: shared-output authoring surface passes schema validation
- **WHEN** workflow YAML 包含 `workflow.resources.books` 且不包含已移除的 workflow-level 写入 intents
- **THEN** schema-only 校验 MUST 通过

