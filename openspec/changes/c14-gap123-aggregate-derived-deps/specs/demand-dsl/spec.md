## ADDED Requirements

### Requirement: aggregate derived fields MUST support dependency-driven evaluation (DAG)
系统 MUST 将 `outputs.*.aggregate.fields` 中的 rank/post 字段视为同一套聚合后派生字段图(DAG),并在 finalize 阶段按拓扑序执行,以支持:

- `rank.by` / `rank.order_by` 引用聚合后派生字段(例如 ratio、all_integral)
- post 字段(例如 `call_by`)依赖其它 post 字段(例如 `score_by_rank` 的结果)
- 综合分后的二次排名(rank-after-post)

系统 MUST 检测循环依赖并给出可操作的错误提示.

#### Scenario: rank-by-ratio is supported
- **GIVEN** ratio 在 aggregate 内由派生字段产生
- **WHEN** rank 字段以 `by: ratio` 引用该派生字段
- **THEN** 编译期校验 MUST 通过,且运行时 MUST 产生稳定可预测的排名结果

#### Scenario: post depends on post is supported
- **GIVEN** `all_integral` 的 `call_by` 引用其它 post 字段(例如 `score1`/`score2`)
- **WHEN** demand 被编译并运行
- **THEN** 编译期校验 MUST 通过,且 `all_integral` MUST 使用依赖字段的计算结果

### Requirement: aggregate fields MUST support safe compute derived fields (`compute`)
系统 MUST 支持在 `outputs.*.aggregate.fields.<out_field_id>` 中声明 `compute: <expression>` 以产生聚合后派生字段,并满足:

- `compute` MUST 使用安全表达式引擎执行(与 `where`/顶层 `fields.*.compute` 一致的安全边界)
- `compute` 的依赖字段 MUST 在编译期被提取并用于 DAG 执行计划与循环依赖诊断
- `compute` 字段 MUST 可被 `rank.by`/`rank.order_by` 与其它派生字段(`compute`/`call_by`/`score_by_rank`)引用

#### Scenario: compute ratio then rank-by-ratio is supported
- **GIVEN** ratio 在 aggregate 内由 `compute` 产生(例如 `ratio = sum_a / sum_b`)
- **WHEN** rank 字段以 `by: ratio` 引用该派生字段
- **THEN** 编译期校验 MUST 通过,且运行时 MUST 产生稳定可预测的排名结果

#### Scenario: compute depends on post is supported
- **GIVEN** `total` 的 `compute` 引用其它 post 字段(例如 `s1`/`s2`)
- **WHEN** demand 被编译并运行
- **THEN** 编译期校验 MUST 通过,且 `total` MUST 使用依赖字段的计算结果
