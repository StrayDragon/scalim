# yaml-dsl-workflow Specification（变更：workflow 阶段调度）

## ADDED Requirements

### Requirement: yaml_dsl workflow runtime entrypoints MUST 通过 WorkflowRuntimeOptions 暴露 scheduler preset
系统 MUST 允许调用方通过运行入口（runtime entrypoints）配置 workflow 的 scheduler preset：

- `run_workflow(..., workflow_runtime_options=WorkflowRuntimeOptions(scheduler=...))` MUST 接受 scheduler preset 对象
- 该配置 MUST 位于运行期策略边界（runtime policy boundary）（不得引入新的 YAML authoring surface 字段）
- 当调用方未显式提供 scheduler 时，默认值 MUST 等价于 `pipeline`

#### Scenario: scheduler preset 通过运行入口配置（而非 YAML）
- **GIVEN** workflow YAML 仅声明 `workflow.runs` 与 `depends_on`
- **WHEN** 调用方以 `workflow_runtime_options.scheduler=stage_barrier` 运行 workflow
- **THEN** 系统 MUST 以 stage_barrier 语义调度执行
- **AND** workflow YAML 本身 MUST 无需新增任何字段即可表达该行为

### Requirement: yaml_dsl public facade MUST 在稳定路径导出 scheduler preset 类型
系统 MUST 在稳定导入路径上暴露 workflow scheduler preset 的类型，以便调用方以最小成本配置：

- `scalim.dsl.yaml_dsl.workflow_types` MUST 导出 `PipelineSchedulerOptions`
- `scalim.dsl.yaml_dsl.workflow_types` MUST 导出 `StageBarrierSchedulerOptions`

#### Scenario: 调用方可从稳定 facade 导入 scheduler preset
- **WHEN** 调用方执行 `from scalim.dsl.yaml_dsl.workflow_types import PipelineSchedulerOptions, StageBarrierSchedulerOptions`
- **THEN** 导入 MUST 成功
