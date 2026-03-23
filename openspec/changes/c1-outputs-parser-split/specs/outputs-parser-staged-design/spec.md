# outputs-parser-staged-design Specification

## Purpose
定义 outputs 解析的阶段化架构（staged parsing），降低复杂度并提升可测试性。

## ADDED Requirements

### Requirement: outputs parsing MUST be staged and testable
系统 MUST 将 outputs 解析按职责拆分为可组合阶段（结构解析、继承/引用解析、语义校验、衍生信息产出），并确保每个阶段可被单元测试覆盖。

#### Scenario: from-cycle is detected deterministically in the resolution stage
- **GIVEN** outputs 中存在 `from` 引用环
- **WHEN** 系统执行 outputs 解析
- **THEN** MUST fail-fast
- **AND** 错误信息 MUST 指出发生 cycle 的 output name（或等价诊断）
