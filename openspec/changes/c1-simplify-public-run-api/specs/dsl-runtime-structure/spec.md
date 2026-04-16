# dsl-runtime-structure Specification

## Purpose
为 `scalim.dsl.yaml_dsl` 的公开运行入口收敛运行期契约结构：

- 公开入口必须以 **单一 `options` 对象**驱动，且 `workflow` 入口也必须满足该约束（不再通过额外 kwargs 拼装运行期策略）。
- 运行期 knobs 必须正交分组、可在构造/合并阶段 fail-fast 校验，避免“超大扁平 options”导致的隐含规则与不一致。
- 输出写出/捕获/tee 语义必须显式表达，且 `demand` 与 `workflow` 的规则边界一致。
- 公共 facade 必须收口到最小 surface：移除注入/测试专用参数，避免用户材料固化内部实现结构。

## ADDED Requirements

### Requirement: public run entrypoints MUST keep a single `options` object per entrypoint
系统 MUST 保持公开运行入口为“单一 `options` 对象驱动”，且 `workflow` 入口也 MUST 将其所有运行期策略（例如 runtime options、path aliases、per-run patches）收敛在该 `options` 对象内，而不是通过额外参数拼装。

> 注：本条要求的是“每个入口只有一个 options 参数”，不要求不同入口复用同一个 options 类型。

#### Scenario: workflow entrypoint takes only `options`
- **GIVEN** 调用方运行 `workflow`
- **WHEN** 调用方调用公开入口
- **THEN** 公开入口 MUST 只接受一个 `options` 对象作为运行期契约承载
- **AND** 原本作为独立参数出现的 knobs MUST 迁移到 `options` 的子结构中

系统 MUST 在构造期进行 fail-fast 校验（在 `RunOptions`/其子对象的 `__post_init__` 或等价位置），使非法组合在进入执行链路前即可被拒绝。

#### Scenario: invalid option combinations are rejected before execution
- **GIVEN** 调用方构造运行入口的 `options` 对象
- **WHEN** `options` 中出现违反安全边界或输出策略约束的非法组合
- **THEN** 系统 MUST 在构造/校验阶段 fail-fast 抛出异常
- **AND** 异常信息 MUST 指向冲突的字段/分组,便于调用方修正

### Requirement: public options MUST split demand vs workflow concerns (no mixed `RunOptions`)
系统 MUST 将独立 `demand` 与 `workflow` 的公开运行契约拆分为两个类型（例如 `DemandRunOptions` 与 `WorkflowRunOptions`），并在 `workflow` options 中以显式子对象承载默认的 `demand` options（例如 `WorkflowRunOptions.demand`）。

系统 MUST 避免继续扩大单一“扁平 `RunOptions`”公开字段集合（尤其是同时服务 demand/workflow 两种入口的字段），以消除“哪些字段在 workflow 无效”的记忆负担。

#### Scenario: workflow uses embedded demand options
- **GIVEN** 调用方运行 `workflow`
- **WHEN** 调用方构造 `WorkflowRunOptions`
- **THEN** 系统 MUST 提供一个明确的子对象用于承载每个节点默认的 demand options（例如 `options.demand`）
- **AND** per-run patch MUST 以该子对象为主要 patch 目标（而不是 patch workflow 本身）

### Requirement: output capture/write/tee semantics MUST be explicit and consistent across demand/workflow
系统 MUST 将“是否落盘/是否保留内存/是否镜像(tee)”等选择以显式、强类型的输出策略表达，而不是通过“额外传入一个参数即可隐式改变 sink 行为”的方式组合语义。

系统 MUST 在公开运行入口中移除 `sink` 这类会引入隐式 tee 语义的参数/字段；若框架内部仍使用 `sink` 概念，其必须属于 internal/execution 层边界，不得作为 DSL public facade 的运行期契约暴露。

系统 MUST 确保 demand 与 workflow 的输出/捕获规则边界一致：相同的输出策略输入在两条入口链路中应得到一致的行为。

#### Scenario: demand file output plus capture does not change behavior implicitly
- **GIVEN** 调用方运行一个会产生文件输出的 demand/workflow
- **WHEN** 调用方同时启用“写文件”与“捕获到内存”
- **THEN** 系统 MUST 通过显式输出策略表达“tee”这一组合
- **AND** 系统 MUST NOT 通过“额外传入一个参数”隐式推导 tee

### Requirement: workflow per-run patch MUST be explicit and policy-aware
系统 MUST 为 `workflow` 提供 per-run patch 能力，但该 patch MUST 满足：

- patch 的对象是 “节点的 demand options”（例如 `WorkflowRunOptions.demand`），而不是 “workflow 自身的 runtime options”
- patch 的可变更字段集合 MUST 明确，并在合并阶段 fail-fast 校验
- patch MUST NOT 覆盖安全边界（例如 allowlist/trusted mode 等）

#### Scenario: illegal patch to security boundary is rejected
- **GIVEN** 调用方为某个 run_id 提供 patch
- **WHEN** patch 尝试覆盖安全边界字段
- **THEN** 系统 MUST fail-fast 拒绝该 patch
- **AND** 错误信息 MUST 指向具体 run_id 与字段路径，便于修正

### Requirement: public workflow facade MUST NOT expose injection/test-only knobs
系统 MUST 收口 workflow 入口的 public surface：`scalim.dsl.yaml_dsl.run_workflow` 这类公共 facade MUST NOT 暴露注入型/测试专用参数（例如 `run_ir_fn` / `compile_demand_yaml_fn`），且这些注入点也 MUST NOT 出现在公开 options 对象中。

若框架内部仍需要这些注入点，系统 MUST 将其放置在 internal/test-only 边界（例如 `scalim.dsl.yaml_dsl._internal.workflow_injected_entrypoints.run_workflow_injected` 或 tests 专用 helper），避免用户材料固化内部实现结构。

#### Scenario: passing injection knobs to public facade fails fast
- **WHEN** 调用方对 `scalim.dsl.yaml_dsl.run_workflow` 传入 `run_ir_fn` 或 `compile_demand_yaml_fn`
- **THEN** 该调用 MUST 失败（参数不存在或被拒绝）
- **AND** 错误信息 SHOULD 指向 internal/test-only 注入入口或迁移方式（例如 `scalim.dsl.yaml_dsl._internal.workflow_injected_entrypoints.run_workflow_injected`）
