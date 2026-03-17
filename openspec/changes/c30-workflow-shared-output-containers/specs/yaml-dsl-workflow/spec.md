## ADDED Requirements

### Requirement: workflow MUST support shared output containers across runs
系统 MUST 扩展 workflow YAML 语义,支持在 workflow 层声明共享输出容器(例如 workbook/csv resource),并将多个 run 的输出合并写入该共享容器.
系统 MUST 定义确定性写入顺序(以 workflow 声明顺序为准),并且 MUST NOT 依赖并发完成顺序.

说明: 该变更为 **DELAYED** 提案;此 delta spec 仅用于明确需求边界并通过结构校验,不代表已进入实现排期.

#### Scenario: writes to a shared workbook are deterministic
- **GIVEN** 两个 runs 写入同一个共享 workbook 的不同 sheet
- **WHEN** workflow 在并发模式下执行
- **THEN** 对共享资源的写入顺序 MUST 由 workflow 声明顺序决定,且结果 MUST 可复现
