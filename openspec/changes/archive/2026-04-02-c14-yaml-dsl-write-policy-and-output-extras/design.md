## Context

当前输出面存在四类容易混淆的配置:

- 资源声明与运行期覆盖: `resources.books/files`
- 资源级默认写策略: `resources.books.*.write_defaults`
- 输出级写策略: `outputs[*].write`
- 输出附加内容: `meta` / `audit`

它们共同造成的问题不是单个字段本身复杂,而是“概念边界不清晰”:

- 什么是资源声明,什么是 runtime overlay
- 什么是资源默认值
- 什么是输出本体 override
- 什么是运行期附加能力

## Goals

- 明确 `resources` 的声明 vs overlay 分层
- 定义 write policy 的单一 SSOT
- 把输出附加能力与写策略分层
- 为 typed overrides 提供明确职责边界

## Non-Goals

- 不重新设计整个 output model
- 不讨论 imports 的完整 allow matrix

## Final Direction

### 1. `resources.books/files` 继续保留为 authoring 资源声明面

从当前代码路径看,`resources` 并不是单纯的“运行期附带参数”,而是参与了编译与绑定:

- `outputs[*].to.file` / `to.book` / `to.sheet` 直接绑定 `resources.files` / `resources.books`
- demand 可以独立运行,因此 demand YAML 内的 `resources` 需要独立描述可写目标
- workflow 编译期会汇总各 demand 的资源定义,检查冲突,并允许 `workflow.resources` / `RunOverrides.resources` 做覆盖

因此 `resources` 的主职责应明确为:

- 资源 identity: `book_id` / `file_id`
- 资源 kind: 例如 `csv_file` / `xlsx_file` / `xlsx_memory`
- 资源拓扑与导出目标: `path` / `budget` / `export_xlsx`
- 与该资源实例直接绑定的 IO 特性: 例如 `encoding` / `allow_formulas` / `write_lock`

这部分仍属于 authoring surface,因为没有它就无法稳定表达“输出写到哪里、写到哪类目标上”。

### 2. `workflow.resources` 与 `RunOverrides.resources` 明确是 overlay

当前实现已经有很清晰的 overlay 语义:

- `workflow.resources` 会先被转成 `ResourcesOverride`
- 用户传入的 `RunOverrides.resources` 再在其上做 deep-merge
- merge 不是整体替换,而是按 `books/files/<id>` 以及子字段分别覆盖

代码里已经体现这一点:

- `RunOverrides.resources` 文档明确声明是 `overlay/deep-merge`
- `workflow_entrypoints.py` 中对 `budget` / `export_xlsx` / `write_defaults` 都有字段级 merge

因此本提案的方向不是再发明一套 precedence,而是把现有现实收敛成明文规则:

- YAML `resources` = 基础声明
- workflow 资源 = 编排层 overlay
- Python `RunOverrides.resources` = 最终运行入口 overlay

### 3. `resources.books.*.write_defaults` 应成为 workbook 写策略的单一 SSOT

当前 workflow 编译链已经按这个方向工作:

- `_effective_write_defaults(book)` 先取 `resources.books.<id>.write_defaults`
- `outputs[*].write` 再作为 overlay 去覆盖 `mode/align_by/header_policy/on_mismatch/on_conflict`

这说明当前重复建模点正是:

- 资源级默认策略
- 输出级再次声明同一组 workbook 写策略

本提案的最终收敛方向是:

- `resources.books.*.write_defaults` 作为 workbook 级默认写策略 SSOT
- `outputs[*].write` 收缩为 output-local 行为,只保留与该输出自身展示/表头相关的最小字段

按当前代码语义,最明确应保留在 output 层的最小集合是:

- `include_header`
- `header_fields_output_by`

而以下字段应以 book 默认策略为主,不再作为长期双入口保留:

- `mode`
- `align_by`
- `header_policy`
- `on_mismatch`
- `on_conflict`

这会要求后续 runtime typed overrides 也同步把“改 workbook 写策略”和“改单个 output 展示细节”分开表达。

### 4. `meta` / `audit` 是真实的 extra-sheet 能力,不是抽象 metadata

这两个开关当前的实际行为很具体:

- `meta` 会生成额外 workbook sheet,写入运行信息与统计
- `audit` 会生成额外 workbook sheet,写入目标失败等审计信息

代码和文档证据都很直接:

- `output_composition_yaml.py` 会把它们编译成 `MetaSheetSpec` / `AuditSheetSpec`
- `user-guide.md` 的示例明确把它们和多 sheet 输出并列使用
- 测试覆盖了:
  - 没有 workbook path 时 `meta` 编译失败
  - 没有任何 outputs 时 `meta/audit` 不成立
  - 当运行期 `RunOverrides.outputs` 改成非 workbook 输出后,未显式给 `meta.path` 时它们可能被跳过

因此这里不应再把 `meta/audit` 讨论成“写策略的一部分”。它们本质上是:

- 输出附加能力
- 强依赖 workbook 上下文的 runtime composition

本提案的最终方向是:

- 把 `meta/audit` 与 write policy 明确分层
- 把它们迁出 YAML 主线,收敛到 runtime typed output extras,而不是继续和主线 authoring 输出表面混在一起

### 5. 一个更清晰的边界模型

基于当前实现,本提案最终希望把四层责任拆开:

- `resources.books/files`: 声明“输出目标是什么”
- `resources.books.*.write_defaults`: 声明“这个 workbook 默认怎么写”
- `outputs[*].to/fields/...`: 声明“这个 output 写什么”
- `meta/audit` 等 output extras: 声明“运行后额外附加什么 workbook 产物”

这样后续 schema、runtime overrides 与文档才能按同一分层收敛。


## Dependencies

- 这个 change 的结论会影响 demand imports scope,因为 imports 是否允许进入某个节点取决于它是否还留在 authoring surface
