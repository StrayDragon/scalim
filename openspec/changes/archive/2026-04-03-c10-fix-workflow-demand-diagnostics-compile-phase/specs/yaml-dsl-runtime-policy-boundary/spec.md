## MODIFIED Requirements

### Requirement: extracted runtime policy MUST be controllable by runtime entrypoints and environment selection
迁出后的 runtime policy MUST 由运行入口显式控制:

- Python / CLI runtime entrypoints MUST 提供 typed surface
- 对性能损耗显著的 guardrails,系统 MUST 支持按环境启停
- workflow compile 期间若为结构预加载 demand YAML，系统 MUST NOT 在尚未拿到 effective runtime policy 前抢跑 runtime-only diagnostics

#### Scenario: expensive guardrails are enabled only in selected environments
- **WHEN** 某个 guardrail 在开发环境需要开启而生产环境需要关闭
- **THEN** 用户 MUST 能通过 runtime entrypoint 或环境选择切换该行为
- **AND** 不需要修改 YAML authoring 文件

#### Scenario: workflow compile does not preempt demand diagnostics policy
- **GIVEN** 某个 workflow run 引用的 demand YAML 含有 intentional duplicate effective field display names
- **WHEN** 系统执行 workflow compile 阶段的结构预加载
- **THEN** 系统 MUST NOT 因 `validate_unique_field_names` 在该阶段直接失败
- **AND** duplicate-name 诊断 MUST 等到具备 effective runtime policy 的 demand compile 边界再决定是否报错
