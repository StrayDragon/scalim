## REMOVED Requirements

### Requirement: demand MUST bind outputs to books via `outputs_defaults.to.book` and `outputs[*].to`
**原因**：`outputs_defaults` 顶层默认值容器已被破坏性移除,输出绑定不再允许依赖 `outputs_defaults.to.book` 的隐式继承。

**迁移**：为每个 Excel output 显式提供 `outputs[*].to.book`,并用 YAML anchors(`_templates`) 或 `$import` 片段在 `outputs[*].to` 局部复用该字段。

## ADDED Requirements

### Requirement: demand MUST bind outputs to books via `outputs[*].to.book` and `outputs[*].to.sheet`

系统 MUST 支持在 demand YAML 中将 Excel outputs 绑定到 book 资源,且绑定入口仅允许位于 output 局部:

- 对于 **未声明 `container`** 的 output(表示 Excel 输出),`outputs[*].to` MUST 存在且 MUST 为 mapping:
  - `outputs[*].to.book` MUST 为非空字符串
  - `outputs[*].to.sheet` MAY 为非空字符串

默认/继承规则:

- 若 `outputs[*].to.sheet` 缺省,则 `sheet` MUST 默认等于 `outputs[*].name`
- `sheet` MUST 通过 Excel sheet 名校验(非空、长度 `<=31`、且不得包含 `\\ / ? * [ ] :`)
- 若某 output 的 effective `to.book` 缺失,系统 MUST fail-fast 并给出可复制迁移提示(例如提示设置 `outputs[*].to.book`)

#### Scenario: sheet defaults to output.name and is validated
- **GIVEN** `outputs[0].name: metrics`
- **AND** `outputs[0].to.book: report`
- **AND** `outputs[0].to.sheet` 缺省
- **WHEN** 系统计算 effective IO binding
- **THEN** `outputs[0]` MUST 绑定到 book=`report`, sheet=`metrics`

#### Scenario: invalid default sheet name fails fast
- **GIVEN** `outputs[0].to.book: report`
- **AND** `outputs[0].name` 长度大于 31
- **AND** `outputs[0].to.sheet` 缺省
- **WHEN** 系统计算 effective IO binding
- **THEN** MUST fail-fast
- **AND** 错误信息 MUST 指向 `outputs[0].name` 并提示显式提供 `outputs[0].to.sheet`

## MODIFIED Requirements

### Requirement: standalone demand MUST fail-fast when a referenced book resource is missing

系统 MUST 在 standalone `compile/run` 执行 demand 时,对所有 outputs 的 effective `to.book`(来自 `outputs[*].to.book`)执行资源存在性校验,并在缺失时 fail-fast:

- 系统 MUST 确保该 `book_id` 在 effective `resources.books` 中存在
- 若缺失,系统 MUST fail-fast(不得静默降级为“无输出”或“写到临时路径”)
- 错误信息 MUST 同时包含:
  - 缺失的 `book_id`
  - 发生位置(例如 `outputs[0].to.book`)
  - 可复制迁移提示(例如: “在 demand 中声明 `resources.books.<id>` 或在 Python overrides 的 `overrides.resources.books` 提供该资源”)

#### Scenario: missing book id fails fast with actionable hint
- **GIVEN** demand 声明 `outputs[0].to.book: report`
- **AND** demand 未声明 `resources.books.report`
- **WHEN** 调用方执行 standalone `compile/run` 且未提供 `overrides.resources.books.report`
- **THEN** MUST fail-fast
- **AND** 错误信息 MUST 提示如何补齐 `resources.books.report`

### Requirement: `.xlsx` outputs MUST use books binding; legacy workbook container surface MUST be rejected (BREAKING)

系统 MUST 将 `.xlsx` 输出的用户侧 authoring surface 收敛到 `resources.books` + outputs→book 绑定,并拒绝旧 workbook container 输出写法(避免双路径导致心智负担与实现漂移).

约束:

- `outputs[*].container.type=workbook` MUST 在 schema-only 与 runtime semantic 校验阶段被拒绝
- `outputs[*].container.sheet/allow_formulas/write_lock` MUST 不再作为输出层 authoring surface(其语义移动到 `outputs[*].to.sheet` 与 `resources.books.*` 中)
- 若用户仍需要 CSV 文件输出,仍可继续使用 `outputs[*].container.type=csv` + 非空 `path`

#### Scenario: schema rejects legacy workbook container surface deterministically
- **WHEN** demand YAML 仍采用旧 workbook container 输出写法
- **THEN** schema-only 校验 MUST 失败
- **AND** 错误信息 MUST 提示迁移到 `resources.books` + `outputs[*].to`(显式 `to.book/to.sheet`)

