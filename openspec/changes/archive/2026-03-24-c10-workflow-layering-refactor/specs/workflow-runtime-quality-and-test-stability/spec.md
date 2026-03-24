## MODIFIED Requirements

### Requirement: workflow entrypoints MUST support dependency injection without module-global mutation
系统 MUST 支持对 workflow 执行关键依赖（至少包括 `run_ir` 与 demand 编译回调）进行**每次调用级别**的显式依赖注入（用于单测与内部替换）,且该机制 MUST 不通过写模块全局变量实现,以保证并发执行可预期。

建议通过 `IMPL_ROOT.dsl.by_yaml.workflow_entrypoints.run_workflow(..., run_ir_fn=..., compile_demand_fn=...)`（或等价入口）完成注入。

#### Scenario: injected executor does not cross-contaminate concurrent runs
- **WHEN** 两个并发的 workflow 执行分别使用不同的注入执行器/编译回调
- **THEN** 每次执行 MUST 只调用其自身注入的依赖,不得互相污染

