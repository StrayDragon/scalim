## ADDED Requirements

### Requirement: demand imports MUST remain available for reusable authoring fragments
demand `imports` / `$import` MUST 继续服务于跨文件 authoring 复用:

- imports MUST 继续支持 demand 侧片段共享
- 允许范围 MUST 绑定到稳定 authoring surface,而不是 runtime overlay / control-plane

#### Scenario: demand reuses a resource declaration fragment from another file
- **GIVEN** 某个 demand YAML 通过 `imports` 引入外部片段文件
- **WHEN** 用户在 `resources.books.report` 或 `resources.files.detail_csv` 中使用 `$import`
- **THEN** 系统 MUST 成功展开该 authoring 片段

### Requirement: demand imports scope MUST be limited to stable authoring surfaces
`$import` 的允许范围 MUST 限制在 demand 的稳定 authoring surfaces:

- `main_source`
- `sources.*`
- `fields.*`
- `relations.*`
- `resources.*` 中仍属于资源声明的部分

#### Scenario: runtime-policy paths are not importable
- **WHEN** 用户尝试在 runtime-policy 或 output extras 路径中使用 `$import`
- **THEN** 系统 MUST 拒绝该写法
- **AND** MUST 给出 imports scope 不包含该路径的诊断

### Requirement: workflow MUST NOT support imports expansion
workflow MUST NOT 支持 imports expansion:

- workflow schema MUST 不暴露 `$import` 作为受支持结构
- workflow validate / compile MUST 不接受 workflow fragment imports 作为主线路径

#### Scenario: workflow import syntax is rejected
- **GIVEN** 某个 workflow YAML 试图声明 `imports` 或 `$import`
- **WHEN** 用户执行 workflow validate 或 schema 校验
- **THEN** 系统 MUST 拒绝该结构

### Requirement: imports MUST NOT become a substitute for runtime overlay or output extras
imports MUST 仅解决“跨文件共享 authoring 片段”的问题,而不是替代 runtime overlay、profile 或 output extras:

- imports MUST NOT 用于重建 runtime policy 配置面
- imports MUST NOT 用于恢复已迁出的 output extras authoring surface

#### Scenario: imports is evaluated by reuse value rather than overlay convenience
- **WHEN** 某个新字段希望接入 imports
- **THEN** 审核标准 MUST 先判断它是否属于稳定 authoring surface
- **AND** 若该字段本质是 runtime overlay 或 output extras,则 MUST NOT 接入 imports
