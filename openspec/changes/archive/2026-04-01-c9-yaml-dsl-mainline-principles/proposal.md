## Why

当前 YAML DSL 的后续讨论已经自然分成两层:

- 顶层原则: 主线未来应该朝什么方向收敛
- 具体专题: workflow drift、observability、runtime policy、write policy、imports 等

后者适合进入更具体的专题提案,但前者仍需要一个明确归宿。否则各个专题提案会反复重复解释“为什么整体要往这个方向走”,还容易在优先级和边界上出现漂移。

因此需要一个很小但明确的 umbrella-level 提案,专门承接“主线原则”,而不再夹带具体策略细节。

## What Changes

- 定义 YAML DSL 主线收敛的基础原则:
  - 单主线演进,不引入 `dsl_version`
  - 不维护并行 schema / parser / validator
  - `YAML = authoring`, `Python/CLI = runtime policy`
  - `KV-first`
  - 维护成本与可读性优先于保留低频边缘旋钮
  - workflow 保持“小而声明式”的 orchestration surface
  - workflow 不扩张 imports expansion
- 定义拆分后的 change 依赖顺序与责任边界
- 为后续专题提案提供总提案级基线

## Scope

包括:
- 主线原则与边界
- change 分解与优先级
- 各子提案之间的依赖关系

不包括:
- 任何单个专题的最终字段级策略
- schema/runtime drift 的具体修复
- LSP/editor 内部语义接口的详细设计

## Expected Outcome

- 后续 `c1*` 子提案有统一的上位约束
- 主线收敛方向有独立、可审阅的原则提案
- 审核时可以区分“总方向是否认可”与“某个专题策略是否认可”
