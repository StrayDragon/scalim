# workflow-runtime-module-organization (delta) Specification

## ADDED Requirements

### Requirement: workflow execution MUST be structured as explicit Controller + State with injected dependencies

workflow 执行层本质为状态驱动的调度与生命周期管理，系统 MUST 将其实现建模为显式的 Controller/State 结构以降低回归风险并提升可测试性：

- 系统 MUST 提供一个显式的 `WorkflowRunState`（或等价 dataclass）集中承载执行状态（ready/submitted/outcomes/node_state/capture 等），避免通过散落的 dict/闭包隐式共享状态
- 系统 MUST 提供一个 `WorkflowRunController`（或等价对象）作为执行协调器：
  - 依赖（executor/resource_manager/instrumentation/cache_pool 等）MUST 通过构造参数显式注入
  - 关键状态转换应由明确方法表达（例如 submit/process_done/finalize）
- 逻辑拆分 SHOULD 优先抽离可单测的纯规则模块（failure_policy 决策、outcome 构造、事件分类），避免仅把复杂度从单个长函数扩散到多个仍共享隐式状态的函数

#### Scenario: controller methods can be unit-tested around state transitions
- **GIVEN** 一个 controller 持有显式 state 与注入依赖
- **WHEN** 模拟 future 完成/失败/取消等事件输入
- **THEN** 测试 SHOULD 能仅通过断言 state 的变化与注入依赖的调用来验证语义
- **AND** 不需要依赖全链路 workflow 集成测试才能覆盖主要分支矩阵

