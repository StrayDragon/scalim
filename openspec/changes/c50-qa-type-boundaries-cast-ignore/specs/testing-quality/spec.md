# testing-quality (delta) Specification

## ADDED Requirements

### Requirement: runtime type narrowing and `type: ignore` usage MUST be centralized and auditable

在运行时边界（例如 YAML/IR 动态结构解析、反射式调用）处，系统 MAY 使用 `cast()` / `type: ignore[...]` 处理类型系统无法表达的动态性，但 MUST 满足以下治理要求：

- `cast()` 与结构窄化（mapping/list/str）逻辑 SHOULD 通过少量内部 helper 统一实现，避免在业务逻辑中分散重复
- 必须存在的 `type: ignore[...]` MUST 被聚拢到极少数“边界函数”中，并具备明确的语义理由（便于评审与审计）
- 对 `type: ignore[call-arg]` 等动态调用豁免，系统 MUST 通过回归测试矩阵覆盖主要签名形态与 fallback 分支，作为类型系统缺口的护栏

#### Scenario: dynamic call ignore is covered by a signature matrix test
- **GIVEN** 某个边界函数基于 `inspect.signature` 动态选择调用形态
- **WHEN** 该函数面对多种签名形态（positional/keyword-only/**kwargs/无 ctx 等）
- **THEN** 系统 MUST 有测试矩阵覆盖这些形态
- **AND** `type: ignore[call-arg]` MUST 不得扩散到更上层业务逻辑

#### Scenario: YAML parsing uses centralized narrowing helpers
- **WHEN** YAML parsing/validator 需要将 `object` 窄化为 mapping/list/str
- **THEN** 该窄化 SHOULD 复用统一 helper（或等价 SSOT 实现）
- **AND** 业务逻辑应优先处理已窄化的结构化对象而不是反复 `cast()`

