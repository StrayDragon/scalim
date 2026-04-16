# dsl-runtime-structure Specification

## Purpose
为 `scalim.dsl.yaml_dsl` 的公开运行入口收敛运行期契约结构：在保持“单一 `options` 对象驱动入口”的前提下，将运行期 knobs 组织为更正交、更内聚、可被构造期校验的结构化配置，并移除公共 facade 中的注入型参数暴露。

## ADDED Requirements

### Requirement: public run entrypoints MUST keep a single `options` object while grouping orthogonal knobs
系统 MUST 保持公开运行入口为“单一 `options` 对象驱动”，但其内部 MUST 按关注点拆分为若干正交分组（例如：安全边界、编译期输入、执行期策略、输出策略、可观测性），避免继续扩大一个“扁平 `RunOptions`”的公开字段集合。

系统 MUST 在构造期进行 fail-fast 校验（在 `RunOptions`/其子对象的 `__post_init__` 或等价位置），使非法组合在进入执行链路前即可被拒绝。

#### Scenario: invalid option combinations are rejected before execution
- **GIVEN** 调用方构造运行入口的 `options` 对象
- **WHEN** `options` 中出现违反安全边界或输出策略约束的非法组合
- **THEN** 系统 MUST 在构造/校验阶段 fail-fast 抛出异常
- **AND** 异常信息 MUST 指向冲突的字段/分组,便于调用方修正

### Requirement: output capture/tee semantics MUST be explicit and consistent across demand/workflow
系统 MUST 将“是否落盘/是否保留内存/是否镜像(tee)”等选择以显式、强类型的输出策略表达，而不是通过“额外传入一个参数即可隐式改变 sink 行为”的方式组合语义。

系统 MUST 确保 demand 与 workflow 的输出/捕获规则边界一致：相同的输出策略输入在两条入口链路中应得到一致的行为。

#### Scenario: demand file output plus sink does not implicitly change behavior
- **GIVEN** 调用方运行一个会产生文件输出的 demand/workflow
- **WHEN** 调用方额外传入 `sink` 或其它捕获相关参数
- **THEN** 系统 MUST NOT 通过隐式 tee 推导改变写出语义
- **AND** 系统 MUST 要求调用方通过显式输出策略表达是否需要 tee/保留内存

### Requirement: public workflow facade MUST NOT expose injection/test-only knobs
系统 MUST 收口 workflow 入口的 public surface：`scalim.dsl.yaml_dsl.run_workflow` 这类公共 facade MUST NOT 暴露注入型/测试专用参数（例如 `run_ir_fn` / `compile_demand_yaml_fn`）。

若框架内部仍需要这些注入点，系统 MUST 将其放置在 internal/test-only 边界（例如 `scalim.dsl.yaml_dsl.workflow_entrypoints` 的内部入口或 tests 专用 helper），避免用户材料固化内部实现结构。

#### Scenario: passing injection knobs to public facade fails fast
- **WHEN** 调用方对 `scalim.dsl.yaml_dsl.run_workflow` 传入 `run_ir_fn` 或 `compile_demand_yaml_fn`
- **THEN** 该调用 MUST 失败（参数不存在或被拒绝）
- **AND** 错误信息 SHOULD 指向新的 internal/test-only 注入入口或迁移方式
