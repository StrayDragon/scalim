## Why

当前 YAML DSL 的输出 authoring surface 分裂为两套模型:

- CSV 使用 `outputs[*].container`
- Excel/books 使用 `resources.books` + `outputs[*].to` / `outputs[*].write`

这导致用户需要同时理解两套绑定语义,也让 schema、runtime、overrides、workflow compile 与文档维护长期背着双路径分支。既然 books 路径已经成为 `.xlsx` 的稳定 surface,CSV 也应收敛到同一套 `resources + to + write` 模型。

## What Changes

- **BREAKING**: 移除 `outputs[*].container` 作为用户侧输出绑定语法; CSV/Excel 均统一到 `resources + outputs[*].to + outputs[*].write`.
- 新增文件资源 surface: `resources.files.<file_id>` + `outputs[*].to.file`.
- 将 CSV 现有写入选项迁移到 `outputs[*].write`:
  - `include_header`
  - `header_fields_output_by`
  - 以及与文件输出相关的统一写入策略字段
- 保留并收敛 books surface:
  - `resources.books.<book_id>`
  - `outputs[*].to.book` / `outputs[*].to.sheet`
  - `outputs[*].write.*`
- 更新 runtime overrides / workflow compile / validation / docs / schema,使 CSV 与 books 共享同一套输出建模与错误路径。
- 不提供兼容写法或双入口保留; 旧 `container` 直接 fail-fast 并给出迁移提示。

## Capabilities

### New Capabilities
- `yaml-dsl-file-resources`: 为非 workbook 文件输出提供统一资源面(`resources.files`)与 `to.file` 绑定语义,取代 `outputs[*].container`.

### Modified Capabilities
- `yaml-dsl-books-resources`: 收敛输出绑定 authoring surface,明确 books 与 files 共用 `to/write` 模型,并移除 `container` 作为并行 surface。
- `yaml-dsl-output-overrides`: 运行期 `overrides.outputs` 改为统一承载 CSV/books 的 `to/write` 结构,不再接受 `container`.
- `yaml-dsl-schema`: schema 改为暴露 `resources.files` / `to.file` / 统一 `write` 字段,并拒绝旧 `outputs[*].container`.
- `output-composition`: 输出编译逻辑改为从统一 target model 生成 CSV/Excel 输出,不再存在 container-vs-books 双分支。
- `yaml-dsl-workflow-validate`: workflow 递归校验与写入节点推导需支持 `to.file`/`to.book` 的统一绑定面,并对旧 `container` 给出迁移诊断。

## Impact

- **YAML authoring**: 所有 CSV 输出都需要从 `container` 迁移到 `resources.files + to.file + write`; books 输出继续使用 `to/write`,但成为唯一稳定范式。
- **Public API / overrides**: `RunOverrides.outputs[*]` 的对外推荐结构统一为 `to + write + fields`; 不再以 `container` 作为 CSV 的运行期 authoring surface。
- **Runtime / workflow**: output composition、workflow compile、validate、introspection 与错误消息将显著简化,但这是一次明确的破坏性重构。
- **Docs & generated artifacts**: 需同步更新 OpenSpec specs、schema SSOT、`demand.gen.json` / `workflow.gen.json`、schema reference 与相关示例; 生成物通过既有入口刷新,不手改 `.gen.*`.
