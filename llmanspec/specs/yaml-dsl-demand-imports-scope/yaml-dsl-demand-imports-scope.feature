# language: zh-CN
# capability: yaml-dsl-demand-imports-scope
# purpose: 定义 demand imports (`imports` / `$import`) 的作用域边界，确保其仅服务于稳定的 authoring 复用场景，而非 runtime overlay 或 output extras 的替代机制。 [rev:c25]
# scope: src/scalim/
功能: yaml-dsl-demand-imports-scope

  @req:r110 @human
  场景: demand imports MUST remain available for reusable authoring fragments
    - demand `imports` / `$import` MUST 继续服务于跨文件 authoring 复用: - imports MUST 继续支持 demand 侧片段共享 - 允许范围 MUST 绑定到稳定 authoring surface,而不是 runtime overlay / control-plane
    假如 某个 demand YAML 通过 `imports` 引入外部片段文件
    当 用户在稳定 authoring surface 中使用 `$import` 引用该片段
    那么 系统 MUST 成功展开该 authoring 片段
  @req:r352 @human
  场景: demand imports scope MUST be limited to stable authoring surfaces
    - `$import` 的允许范围 MUST 限制在 demand 的稳定 authoring surfaces: - `main_source` - `sources.*` - `fields.*` - `relations.*` - `resources.*` 中仍属于资源声明的部分
    当 用户尝试在 runtime policy 或 output extras 等非稳定 authoring surface 中使用 `$import`
    那么 系统 MUST 拒绝该写法
  @req:r473 @human
  场景: workflow MUST NOT support imports expansion
    - workflow MUST NOT 支持 imports expansion: - workflow schema MUST 不暴露 `$import` 作为受支持结构 - workflow validate / compile MUST 不接受 workflow fragment imports 作为主线路径
    假如 某个 workflow YAML 试图声明 `imports` 或 `$import`
    当 系统对该 workflow 进行 schema 校验或编译
    那么 系统 MUST 拒绝该结构
  @req:r557 @human
  场景: imports MUST NOT become a substitute for runtime overlay or output extras
    - imports MUST 仅解决“跨文件共享 authoring 片段”的问题,而不是替代 runtime overlay、profile 或 output extras: - imports MUST NOT 用于重建 runtime policy 配置面 - imports MUST NOT 用于恢复已迁出的 output extras authoring surface
    当 某个新字段希望接入 imports 机制
    那么 审核标准 MUST 先判断它是否属于稳定 authoring surface
