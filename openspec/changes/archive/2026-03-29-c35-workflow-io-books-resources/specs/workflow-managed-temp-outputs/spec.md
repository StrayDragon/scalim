## MODIFIED Requirements

### Requirement: workflow MAY manage temp CSV outputs for write-node consumption
当 demand outputs 仅用于 workflow 写入节点消费时,workflow MAY 托管这些 outputs 的中间态；**当 workflow 选择托管时,系统 MUST** 允许以实现细节选择“内存/临时文件”而不是强制落盘：

- workflow-managed 中间态 MUST NOT 通过 demand YAML authoring surface 暴露(例如 `path: ""` 触发);该类配置 MUST 被视为非法并 fail-fast
- workflow MAY 将上游输出物化为可供写入节点消费的内存表结构 artifact(例如 `InMemoryRows` 或等价结构),以避免临时落盘
- 该 artifact MUST 作为写入节点的上游输出参与 workflow 执行,并在最终写入 consumer 完成后释放
- workflow 失败或取消时,未释放的 workflow-managed artifacts MUST 被统一丢弃；系统 MUST NOT 依赖 managed temp dir 清理来完成该能力

#### Scenario: workflow-managed intermediate output is materialized as an in-memory artifact
- **GIVEN** workflow 执行某个 run 并需要将其输出写入共享 book
- **WHEN** workflow 物化写入节点并执行该 run
- **THEN** 系统 MAY 为该输出产出可供写入节点消费的内存 artifact
- **AND** 系统 MUST NOT 要求通过 YAML 形态显式触发“空路径输出”

#### Scenario: workflow-managed artifact is released after final write consumer
- **GIVEN** workflow 的某个中间态 output 被多个写入节点消费
- **WHEN** 最后一个引用该 output 的写入节点成功完成
- **THEN** 系统 MUST 释放该 output 对应的 workflow-managed artifact

#### Scenario: workflow failure discards unreleased in-memory artifacts
- **GIVEN** workflow 运行过程中已产生 workflow-managed 的内存 artifact
- **WHEN** workflow 因失败或取消而结束
- **THEN** 系统 MUST 丢弃尚未释放的 workflow-managed artifacts
- **AND** 系统 MUST NOT 依赖 managed temp dir 清理来完成该能力
