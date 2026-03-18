## ADDED Requirements

### Requirement: workflow MAY manage temp CSV outputs for write-node consumption
当 demand outputs 仅用于 workflow write nodes 消费时，workflow SHALL 托管这些 outputs 的临时落盘路径与清理语义，以减少 Python glue 并避免临时文件泄漏：
- 仅允许对 `container.type: csv` 的 outputs 托管临时路径；workbook outputs MUST 仍显式声明 path
- 当某个 CSV output 的 `container.path` 省略/为空时：
  - 该 output_id MUST 被 workflow write intents 引用；否则 workflow MUST fail-fast
  - workflow MUST 在 node 物化编译前为该 output 分配一个实际的临时 CSV 路径（位于 run-scoped managed temp dir 内）
  - 该路径 MUST 作为实际输出路径参与执行，并写入 workflow artifacts（供 write nodes 消费）
- workflow MUST 在 commit/discard 后清理 managed temp dir（成功与失败路径都必须覆盖）

#### Scenario: pathless CSV output is managed and cleaned up
- **GIVEN** workflow 的某个 run 产出 CSV output `detail` 且 `container.path` 省略
- **AND** workflow 存在 write intent 引用该 output（例如写入 sheetbook/workbook）
- **WHEN** workflow 执行并成功 commit 或失败 discard
- **THEN** write node MUST 能消费到该 output 的实际 CSV 路径
- **AND** workflow 结束后 managed temp dir MUST 被清理

#### Scenario: pathless CSV output not referenced by writes is rejected
- **GIVEN** 某个 run 的 CSV output `detail` 的 `container.path` 省略
- **AND** workflow 中没有任何 write intent 引用该 output_id
- **WHEN** workflow 被编译/物化编译
- **THEN** 系统 MUST fail-fast 并指出该 output 不能为 pathless（需要被 writes 引用或显式 path）
