## ADDED Requirements

### Requirement: runtime-only policy changes MUST define a boundary coverage matrix

当某个能力被定义为 runtime-only policy（尤其是已从 YAML 主线迁出的字段）时，系统的测试与评审材料 MUST 明确定义其边界覆盖矩阵，至少包括以下层次：

- schema / parse 层
- compile / preload 层
- runtime compile 层
- workflow per-run override 层（如适用）
- user-entry smoke 层

#### Scenario: a moved-out YAML field is reviewed for boundary coverage
- **WHEN** 维护者新增或修改某个已迁出 YAML 主线的 runtime-only policy
- **THEN** review 文档 MUST 指出该 policy 在各层的最早生效边界
- **AND** review 文档 MUST 明确哪些层需要测试覆盖

### Requirement: compile/preload layers MUST be reviewed against premature runtime-policy consumption

对于 runtime-only policy，系统 MUST 在设计与测试评审中显式检查 compile / preload 阶段是否可能提前消费该策略。

#### Scenario: review catches compile-phase policy consumption risk
- **WHEN** 某个 runtime-only policy 会影响 demand / workflow 的运行期诊断或行为
- **THEN** review 文档 MUST 说明 compile / preload 阶段是否允许读取该 policy
- **AND** 若不允许，后续测试计划 MUST 包含“compile phase 不抢跑”的覆盖
