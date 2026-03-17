## ADDED Requirements

### Requirement: workflow MUST declare run dependencies and pass context
系统 MUST 扩展 workflow YAML 语法,允许通过显式依赖声明表达 run 之间的 DAG 关系,并在依赖边上传递有限的 ctx(标量/小集合)以支持多阶段流水线编排.

说明: 该变更为 **DELAYED** 提案;此 delta spec 仅用于明确需求边界并通过结构校验,不代表已进入实现排期.

#### Scenario: dependent runs are scheduled after prerequisites
- **GIVEN** workflow 中 run B 声明依赖 run A
- **WHEN** workflow 在并发模式下调度执行
- **THEN** 系统 MUST 在 run A 成功完成后才启动 run B
