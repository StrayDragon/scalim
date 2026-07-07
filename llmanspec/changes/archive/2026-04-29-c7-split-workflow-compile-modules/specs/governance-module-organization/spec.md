## ADDED Requirements

### Requirement: workflow_compile hotspot MUST be decomposed into responsibility-focused submodules

系统 MUST 将 `workflow_compile.py` 这类多职责热点模块拆分为职责单一的子模块,以降低复杂度并提升可测试性。

拆分后系统 MUST 满足:
- 对外稳定入口(例如 `compile_workflow_ir`)保持可用且行为不变
- 纯规则/校验逻辑 MUST 位于可单测的子模块中(无 IO、输入输出明确)
- IO 相关逻辑(例如 demand YAML 预加载) MUST 与纯规则逻辑分离

#### Scenario: workflow compile remains stable after internal split
- **WHEN** 维护者按职责拆分 `workflow_compile.py` 为多个 `_internal` 子模块
- **THEN** 对外入口 `compile_workflow_ir` 的导入与运行 MUST 保持不变
- **AND** `just qa` MUST 通过
