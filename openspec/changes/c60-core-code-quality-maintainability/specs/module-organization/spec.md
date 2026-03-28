## ADDED Requirements

### Requirement: hotspot modules MUST be splittable and guarded against unbounded growth

系统 MUST 对热点模块提供可维护性护栏：
- 当单个模块超过约定阈值（例如 >1000 行）时,维护者 MUST 拆分为多个职责单一的模块
- 拆分 MUST 保持行为等价,并由自动化回归覆盖（输出/事件/错误语义一致）

#### Scenario: module size guardrail fails fast
- **WHEN** 热点模块超过阈值且继续增长
- **THEN** guardrail gate MUST fail-fast 并提示拆分策略

