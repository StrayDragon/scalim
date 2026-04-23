## Context

YAML DSL 中很多“分支对象”已经统一为 oneOf 分支形态 `{<variant>: {...}}`（例如 `sources.*.normalize`、`outputs[*].aggregate.fields.*` producer keys），但资源面仍保留 `kind: <variant>` discriminator：

- `resources.books.<book_id>`：`kind: xlsx_file|xlsx_memory`
- `resources.files.<file_id>`：`kind: csv_file`

这带来三类问题：

1) authoring 风格不一致：分支对象在不同节点出现不同写法，增加认知负担，且公共字段（如 `write_defaults`）的归属不够直观。
2) schema/validator 复杂：需要基于 `kind` 的 `if/then` 约束与多处 fail-fast 分支逻辑来表达“选择某个分支就必须满足该分支必填字段”的契约。
3) demand `$import` 需要 editor-friendly schema：编辑器侧 schema-only 校验不展开 `$import`，若 schema 过于严格会造成假阳性红线；而 workflow 明确不支持 imports expansion（必须在 schema/parser 层 fail-fast 拒绝）。

同时，books/files 资源已作为对外稳定术语（`resources.books` / `resources.files`），并且 demand/workflow 需要保持统一的 authoring surface（除 imports 支持边界外），因此适合在该节点进行一次性形态升级。

## Goals / Non-Goals

**Goals:**

- 将 `resources.books.*` / `resources.files.*` 升级为 oneOf 分支写法，并在 demand/workflow 两侧对齐。
- 保留 “公共字段 + 分支字段” 并存的写法：`write_defaults` 与分支 key 并列（与 `sources.*.normalize.call_by` 一致）。
- demand 侧继续支持 `$import` 复用资源片段，并使 schema-only 校验不会因 `$import` 未展开产生假阳性。
- workflow 侧继续 **不支持** imports expansion：`imports`/`$import` 在 workflow resources 下必须被拒绝并给出迁移提示。
- 收敛 SSOT/生成物边界并纳入 drift gate：仅改 schema SSOT，统一通过生成入口刷新 `*.gen.json`。

**Non-Goals:**

- 不引入多版本 DSL（不新增 `dsl_version`，不维护并行 parser/validator/schema）。
- 不在本变更中迁移其它 `kind` discriminator 节点（本次仅覆盖 books/files resources）。
- 不兼容保留旧写法（`kind: ...`）的解析路径；旧写法应被明确拒绝并给出迁移提示。

## Decisions

1. **资源节点统一为 oneOf 分支对象（exactly-one variant）**

   - `resources.books.<book_id>` MUST 选择且仅选择一个分支 key：
     - `xlsx_file: <mapping>`
     - `xlsx_memory: <mapping>`
   - `resources.files.<file_id>` v1 仅允许：
     - `csv_file: <mapping>`（保留分支写法以统一风格并为未来扩展预留形态）

   文件资源的 v1 分支字段归属：

   - `csv_file`: `path`(required), `encoding`(optional; 默认 `utf-8`)

2. **公共字段与分支并存：`write_defaults` 保持在分支外**

   `resources.books.<book_id>.write_defaults` 保持为公共字段，与分支并列：

   ```yaml
   resources:
     books:
       report:
         xlsx_file:
           path: ./out
           allow_formulas: false
         write_defaults:
           mode: sheet
   ```

   分支内部只包含该 variant 专属字段：

   - `xlsx_file`: `path`(required), `allow_formulas`(optional)
   - `xlsx_memory`: `budget`(optional), `export_xlsx`(optional)

3. **demand `$import` 的位置与组合：允许“节点级/分支级 import”，并允许与本地 override 并存**

   为了让 `$import` 与公共字段组合更自然，demand 侧允许两种复用方式：

   - 节点级 import：
     - `resources.books.<id>: { $import: ... }`（整个资源节点来自 fragment）
     - `resources.files.<id>: { $import: ... }`
   - 分支级 import：
     - `resources.books.<id>.xlsx_file: { $import: ... }`
     - `resources.books.<id>.xlsx_memory: { $import: ... }`
     - `resources.files.<id>.csv_file: { $import: ... }`

   并且，demand 侧 `$import` **允许与本地键并存**（imports expansion 语义：导入值作为 defaults，本地显式声明覆盖导入值）。例如：

   ```yaml
   resources:
     books:
       report:
         $import: common.resources.books.report
         write_defaults: {mode: append}  # local override
         xlsx_file:
           $import: common.xlsx_file_defaults
           path: ./out  # local override
   ```

   需要特别明确一个边界（避免误解“可以用 node-level `$import` 切换 variant”）：

   - imports expansion 是 **fill merge**（不会删除导入片段中的键）
   - 因此若导入片段已包含某个 variant key（例如 `xlsx_file`），本地再声明另一个 variant key（例如 `xlsx_memory`），展开后可能同时存在两个 variant key，系统 MUST fail-fast
   - 若需要“共享公共字段但本地选择 variant”，建议：
     - 让导入片段只包含公共字段（例如 `write_defaults`），不包含任何 variant key；或
     - 只在分支级使用 `$import`（更直觉，也更不容易踩坑）

   对 editor schema-only 校验的要求：

   - schema MUST 允许 `$import`-only mapping 形态出现于上述位置，以避免未展开时的假阳性（例如分支必填 `path` 不应在 `$import`-only mapping 上触发）。
   - schema SHOULD 允许 `$import + 本地 override` 形态（例如 `$import` 与 `write_defaults` / 分支 key 并存），以避免 editor 侧出现无意义的假阳性红线。
   - workflow schema MUST 不允许 `$import` 出现于任意 workflow resources 路径（与 `yaml-dsl-schema-workflow-alignment` 对齐）。

4. **实现策略：保持内部配置模型稳定，通过适配解析新形态**

   - runtime 内部仍使用既有 `BookConfig` / `FileConfig`（保留 `kind` 字段作为内部统一 discriminator）。
   - demand loader/workflow parser 在解析时从分支 key 推导 `kind`，并把分支 mapping 解包到现有字段上。
   - 所有错误与诊断 path 必须反映新的 authoring 逻辑路径（例如 `resources.books.report.xlsx_file.path`），并在检测到旧 `kind` 写法时给出可复制的迁移提示。

5. **SSOT / 生成物边界与 drift gate**

   - Schema SSOT：`src/scalim/dsl/yaml_dsl/schema_dsl/models/resources.py`
   - 生成物（禁止手工编辑）：
     - `src/scalim/dsl/yaml_dsl/schema/demand.gen.json`
     - `src/scalim/dsl/yaml_dsl/schema/workflow.gen.json`
   - 生成入口：`just gen-yaml-dsl-schema`
   - 质量门禁：至少覆盖 `just gen-yaml-dsl-schema` + drift/QA（如 `just qa` 或既有 schema drift check 目标）。

## Risks / Trade-offs

- **[BREAKING: authoring shape 改动]** → 通过 fail-fast 迁移提示、更新用户文档与示例 YAML 缓解；不保留旧写法的兼容分支以避免长期维护成本。
- **[schema 复杂度上升（oneOf + imports 例外）]** → 在 schema SSOT 中集中表达 oneOf 规则，并对 `$import`-only mapping 使用统一 helper/schema 片段以避免散落复制。
- **[resources.files 仅一个 variant，看似冗余]** → 以风格统一与未来扩展为收益；并通过文档明确该节点 v1 仅支持 `csv_file` 分支。

## Migration Plan

1. 更新 specs：为 books/files resources 的新 authoring 形态补充/替换 requirements 与示例。
2. 更新 schema SSOT 并运行 `just gen-yaml-dsl-schema` 刷新 `*.gen.json`。
3. 更新 demand loader / validator / workflow parser 的 fail-fast 与诊断 path。
4. 更新文档与 fixtures/skills 示例 YAML，并跑 repo 质量门禁（建议 `just qa`）。

## NOTE

- `$import` × oneOf（避免 schema-only 假阳性）：**无需引入跨仓库的额外 schema generator 抽象**；在 schema SSOT 中集中表达“variant exactly-one + `$import`-only 例外 + `$import + override` 允许”，并复用现有 demand/workflow schema 的 imports 边界（demand 暴露 `$import`；workflow 不暴露）。
