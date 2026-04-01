## ADDED Requirements

### Requirement: `resources` MUST distinguish authoring declarations from runtime overlays
输出资源面 MUST 明确区分“authoring 声明”与“runtime overlay”:

- YAML `resources.books/files` MUST 表达基础资源声明
- workflow 资源覆盖与 `RunOverrides.resources` MUST 作为 overlay / deep-merge 生效
- overlay MUST 不改变 `resources` 作为资源 identity 与目标声明面的职责

#### Scenario: workflow and user overlays deep-merge over declared resources
- **GIVEN** 某个 demand YAML 声明了基础 `resources.books.report`
- **AND** workflow 与 `RunOverrides.resources` 都对同一资源补充覆盖字段
- **WHEN** 系统编译并运行该输出
- **THEN** 系统 MUST 以基础声明为底并按 overlay / deep-merge 合成最终资源配置

### Requirement: workbook write policy MUST use `resources.books.*.write_defaults` as the single SSOT
workbook 写策略 MUST 以 `resources.books.*.write_defaults` 为单一 SSOT:

- workbook 级写入行为 MUST 由 `write_defaults` 表达
- `outputs[*].write` MUST 收缩为 output-local 的最小展示/表头 override
- `outputs[*].write` MUST NOT 继续长期承载 workbook 级 `mode`、`align_by`、`header_policy`、`on_mismatch`、`on_conflict`

#### Scenario: output write keeps only local header behavior
- **WHEN** 用户需要为单个 output 调整表头展示行为
- **THEN** 系统 MUST 允许通过 `outputs[*].write.include_header` 与 `header_fields_output_by` 表达
- **AND** workbook 级写入模式 MUST 继续来自 `resources.books.*.write_defaults`

### Requirement: `meta` and `audit` MUST be runtime output extras instead of YAML authoring fields
`meta` 与 `audit` MUST 从 YAML 主线迁出,并收敛为 runtime typed output extras:

- YAML 主线 MUST 不再把 `meta` / `audit` 作为稳定 authoring 字段
- runtime output extras MUST 明确其 workbook 依赖与输出上下文

#### Scenario: audit sheet is configured by runtime output extras
- **WHEN** 用户需要输出 metadata 或 audit workbook sheet
- **THEN** 系统 MUST 通过 runtime typed output extras 完成装配
- **AND** MUST NOT 继续依赖 YAML 顶层 `meta` / `audit`

### Requirement: docs and overrides contracts MUST reflect the four-layer output boundary
输出相关文档与 typed overrides 契约 MUST 反映以下四层分工:

- `resources.books/files` = 输出目标声明
- `resources.books.*.write_defaults` = workbook 默认写策略
- `outputs[*].to/fields/...` = output 内容编排
- runtime output extras = `meta/audit` 等附加产物

#### Scenario: user-facing guidance explains the layered output model
- **WHEN** 用户查阅 YAML DSL 输出相关文档或 runtime override API
- **THEN** 系统 MUST 以四层模型解释各字段职责
- **AND** MUST 不再把 write policy 与 output extras 混成同一入口
