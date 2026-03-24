## MODIFIED Requirements

### Requirement: demand nodes MUST be able to consume sheetbook sheet rows via a built-in loader
系统 MUST 提供内置 loader `scalim.workflow.loaders:sheetbook_sheet_rows`,允许下游 demand 将上游 sheetbook 的某个 sheet 作为 rows 输入使用:

- loader MUST 接收 `params.ref` 映射对象,并满足以下结构:
  - `ref.node`（上游 node id）
  - `ref.sheetbook`（sheetbook 资源 id）
  - `ref.sheet`（sheet 名）
- loader MUST 返回可迭代 rows（每行 MUST 为 JSON-like mapping）
- 系统 MUST 强制依赖闭包可见性: 下游 node 仅允许读取其依赖闭包内上游 nodes 的 sheetbook
- 当引用越界或目标 sheet 不存在时,系统 MUST fail-fast 并提供可诊断摘要

#### Scenario: reading a non-dependency sheetbook is rejected
- **GIVEN** node C 未声明依赖 node A
- **WHEN** node C 的 demand 通过内置 loader 引用 node A 的 sheetbook sheet
- **THEN** 系统 MUST fail-fast 并报告“引用超出 deps 可见范围”

