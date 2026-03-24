## MODIFIED Requirements

### Requirement: shared output is written via explicit workflow write nodes
系统 MUST 将“写入共享资源”的动作建模为 workflow 的显式节点类型,而不是 demand 的隐式后处理:
- 系统 MUST 支持至少两类写入节点:
  - `write_sheet`(写入/覆盖某个 sheet)
  - `append_sheet`(追加写入某个 sheet,具备明确的字段对齐与 header 策略)
- 写入节点 MUST 消费上游 demand 节点的 output artifacts；该 artifact 可以是文件路径 output，也可以是 workflow-managed 的内存 CSV artifact（`InMemoryCsv`）
- YAML authoring surface MAY 提供简写,但编译后语义 MUST 等价于显式 write nodes
- 当写入节点消费的是 workflow-managed 内存 CSV artifact 时，消费完成后系统 MUST 参与该 artifact 的最终消费者释放流程

#### Scenario: write nodes depend on file-backed demand outputs
- **GIVEN** write_sheet 节点消费 run A 的文件路径 output `detail`
- **WHEN** workflow 执行
- **THEN** 系统 MUST 在 run A 成功完成并产生该 output 后才允许 write_sheet 执行

#### Scenario: write nodes can consume in-memory workflow-managed outputs
- **GIVEN** write_sheet 节点消费 run A 的 pathless CSV output `detail`
- **AND** `detail` 被 workflow 托管为内存 CSV artifact
- **WHEN** workflow 执行
- **THEN** 系统 MUST 在 run A 成功完成并发布该 artifact 后允许 write_sheet 执行
- **AND** write_sheet MUST 无需依赖临时 CSV 文件路径即可完成写入
