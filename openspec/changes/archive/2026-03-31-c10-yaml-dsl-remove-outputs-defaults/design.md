## Context

当前 by_yaml demand/workflow 的 Excel 输出绑定面由三部分共同组成:

- `resources.books.<book_id>`: book 资源声明(路径/内存预算/导出/写入默认策略等)
- `outputs[*].to`: output → book/sheet 绑定
- `outputs_defaults.to.book`: 当 `outputs[*].to.book` 缺省时的默认 book 绑定

并且运行期还存在一条额外的 IO-only 覆盖入口:

- `RunOverrides.outputs_defaults` / `overrides.outputs_defaults.to.book`

这使得“book 绑定”存在多处入口(显式绑定、全局默认、运行期默认 patch),对作者与维护者都不直观,且不利于未来扩展输出目的地模型。

## Goals / Non-Goals

**Goals:**

- 删除 YAML 顶层 `outputs_defaults` 字段与其继承语义,使 Excel 输出绑定只依赖 `outputs[*].to.book`.
- 删除运行期 `RunOverrides.outputs_defaults` 及 workflow 编译侧对应分支,减少 IO 绑定入口数量.
- 保持 `outputs[*].to` 与 `outputs[*].write` 分层模型不变.
- 提供清晰、可复制的迁移路径: 使用 YAML anchors(`_templates`) 或 `$import` 片段复用 `to.book` 写法.
- 文档/生成物边界收敛:
  - 不手改任何 `.gen.*` 文件或 injected blocks
  - 通过既有生成入口刷新 schema reference 与示例.

**Non-Goals:**

- 不引入新的输出目的地模型(例如统一 `sink`/`target` 结构);这是未来可能的结构性重建模,不在本变更范围内.
- 不提供兼容/降级路径(例如同时接受旧 `outputs_defaults` 写法);旧写法将直接 fail-fast.
- 不新增新的运行期 patch 语义来替代 `overrides.outputs_defaults`(例如“按名称批量填充 to.book”).

## Decisions

1) **删除 `outputs_defaults` 与默认继承**

- demand YAML 不再允许 `outputs_defaults`.
- Excel 输出必须显式声明 `outputs[*].to.book`.
- 诊断路径统一指向缺失位置: `outputs.<idx>.to.book`(或 `overrides.outputs.<idx>.to.book`).

2) **保留并强化“配置复用属于 YAML authoring 层”**

复用默认 `book` 绑定不再通过 DSL 语义层提供全局默认值,而通过:

- YAML anchors/merge(推荐在 `_templates` 下集中声明模板锚点)
- `$import` 片段导入(跨文件复用)

3) **删除 `RunOverrides.outputs_defaults`**

- 运行期仍保留两条入口:
  - `overrides.outputs`: replace 语义,用于 UI/动态 outputs 编排(可显式提供 `to.book`)
  - `overrides.resources`: overlay 语义,用于覆盖 `resources.books.*` 的 IO 参数(path/budget/export/write_defaults/locks 等)
- 不再提供“运行期默认 book patch”这条特殊分支.

4) **meta/audit 的默认 book 选择保持确定性**

移除 `outputs_defaults` 后:

- standalone demand 的 meta/audit 仍绑定到“第一个 Excel 输出”的工作簿(由 outputs 顺序决定).
- workflow 模式下 meta/audit 写入节点绑定到“第一个 book-bound output”的 book.

当用户需要将 meta/audit 绑定到其它 book 或没有任何 Excel 输出但仍想输出 meta/audit 时,应显式配置 `meta.path`/`audit.path`(standalone),或调整 outputs 顺序/显式输出绑定(workflow)。

## Risks / Trade-offs

- [BREAKING] 旧 YAML 使用 `outputs_defaults.to.book` 将在 schema/validate/compile 阶段 fail-fast → 缓解: 提供迁移指南与示例(anchors/$import),并在错误信息中给出可复制提示.
- [BREAKING] 调用侧使用 `RunOverrides.outputs_defaults` 将编译失败 → 缓解: 指导迁移到 `overrides.outputs`(显式指定 outputs 列表)或仅覆盖 `overrides.resources.books.*`(若只是改路径/预算等).
- 对多 book 输出的 meta/audit 目标选择不再可通过 `outputs_defaults` 指定 → 缓解: 以 outputs 顺序作为确定性选择规则,并在文档中明确“primary Excel output”约定;需要更强表达力可另开 change(例如 `meta.book`),但不在本范围内.

## Migration Plan

1) 迁移 YAML:

- 删除:
  - `outputs_defaults: {to: {book: <id>}}`
- 为每个 Excel output 补齐:
  - `to: {book: <id>, sheet: <name>}` 或在已有 `to` 下增加 `book`
- 推荐复用写法:
  - 在 `_templates` 定义 `&to_<id>` 锚点,通过 `<<: *to_<id>` 注入 `book`.

2) 迁移 Python:

- 删除 `RunOverrides(outputs_defaults=...)` 用法.
- 若需要改写输出绑定,使用 `RunOverrides(outputs=[...])` 显式提供 outputs(含 `to.book`).
- 若只需改变输出路径/导出参数,使用 `RunOverrides(resources={\"books\": {<id>: {\"path\": ...}}})` 覆盖 `resources.books`.

3) 同步文档与生成物:

- 修改 SSOT: OpenSpec specs 与 docs 的手工页.
- 运行 `just gen-docs` 以刷新 `*.gen.*` 与 injected blocks.
- 运行 `just qa` / `just openspec-check` 通过漂移与规范门禁.

## Open Questions

- (none)

