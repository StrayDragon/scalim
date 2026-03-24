## MODIFIED Requirements

### Requirement: workflow MAY manage temp CSV outputs for write-node consumption
当 demand outputs 仅用于 workflow write nodes 消费时，workflow SHALL 托管这些 outputs 的中间态，并避免为 pathless CSV outputs 分配临时落盘路径：
- 仅允许对 `container.type: csv` 的 outputs 托管 workflow-managed 中间态；workbook outputs MUST 仍显式声明 path
- 当某个 CSV output 的 `container.path` 省略/为空时：
  - 该 output_id MUST 被 workflow write intents 引用；否则 workflow MUST fail-fast
  - workflow MUST 让该 output 在 demand 执行完成后物化为 workflow 可消费的内存 CSV artifact（见 `output-composition` 中 `InMemoryCsv` 契约），而不是 run-scoped 临时 CSV 文件路径
  - 该 artifact MUST 作为 write nodes 的上游输出参与 workflow 执行，并在最终 write consumer 完成后释放
- workflow 失败或取消时，未释放的 workflow-managed artifacts MUST 被统一丢弃；系统 MUST NOT 依赖 managed temp dir 清理来完成该能力

#### Scenario: pathless CSV output is materialized as an in-memory artifact
- **GIVEN** workflow 的某个 run 产出 CSV output `detail` 且 `container.path` 省略
- **AND** workflow 存在 write intent 引用该 output（例如写入 sheetbook/workbook）
- **WHEN** workflow 执行该 demand run
- **THEN** 系统 MUST 为 `detail` 产出可供 write nodes 消费的内存 CSV artifact
- **AND** 系统 MUST NOT 要求为 `detail` 分配实际的临时 CSV 文件路径

#### Scenario: pathless CSV output is released after final write consumer
- **GIVEN** workflow 的某个 pathless CSV output 被多个 write intents 消费
- **WHEN** 最后一个引用该 output 的 write node 成功完成
- **THEN** 系统 MUST 释放该 output 对应的 workflow-managed 内存 artifact

#### Scenario: pathless CSV output not referenced by writes is rejected
- **GIVEN** 某个 run 的 CSV output `detail` 的 `container.path` 省略
- **AND** workflow 中没有任何 write intent 引用该 output_id
- **WHEN** workflow 被编译或物化编译
- **THEN** 系统 MUST fail-fast 并指出该 output 不能为 pathless（需要被 writes 引用或显式 path）

#### Scenario: workflow failure discards unreleased in-memory artifacts
- **GIVEN** workflow 运行过程中已产生 workflow-managed 的内存 CSV artifact
- **WHEN** workflow 因失败或取消而结束
- **THEN** 系统 MUST 丢弃尚未释放的 workflow-managed 内存 artifacts
- **AND** 系统 MUST NOT 依赖 managed temp dir 清理来完成该能力
