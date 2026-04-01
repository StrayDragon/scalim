# workflow-managed-temp-outputs Specification

## Purpose
TBD - created by archiving change c50-workflow-managed-temp-outputs. Update Purpose after archive.
## Requirements
### Requirement: workflow MAY manage temp CSV outputs for write-node consumption
当 demand outputs 仅用于 workflow 写入节点消费时,workflow MAY 托管这些 outputs 的中间态；**当 workflow 选择托管时,系统 MUST** 允许以实现细节选择合适的内存 artifact,而不是强制落盘。

- workflow-managed 中间态 MUST NOT 通过 demand YAML authoring surface 暴露(例如 `path: ""` 触发);该类配置 MUST 被视为非法并 fail-fast
- workflow MAY 将上游输出物化为可供写入节点消费的内存 artifact,而不是强制落盘
- 当下游 consumer 为 `xlsx_memory` 写节点时,系统 MUST 为对应 output 提供按 output 粒度的 typed in-memory artifact
- 对 `xlsx_memory` consumer 路径,系统 MUST 保留 `FieldValue` 值域,MUST NOT 强制经过 `CSV` 等价字符串化再做后置恢复
- 若同一 output 同时被 `CSV` 等价 consumer 消费,系统 MAY 从 typed artifact 派生字符串 artifact,但 typed artifact MUST 是 `xlsx_memory` 路径的 SSOT
- 该 artifact MUST 作为写入节点的上游输出参与 workflow 执行,并在最终写入 consumer 完成后释放
- workflow 失败或取消时,未释放的 workflow-managed artifacts MUST 被统一丢弃；系统 MUST NOT 依赖 managed temp dir 清理来完成该能力

#### Scenario: xlsx_memory-bound managed output is materialized as a typed artifact
- **GIVEN** workflow 执行某个 run 并需要将其输出写入共享 `xlsx_memory` book
- **WHEN** workflow 物化写入节点并执行该 run
- **THEN** 系统 MUST 为该 output 提供可供写入节点消费的 typed in-memory artifact
- **AND** 系统 MUST NOT 要求先把该 output 降级为字符串 rows

#### Scenario: typed managed artifact is released after final xlsx_memory write consumer
- **GIVEN** workflow 的某个中间态 output 被多个 `xlsx_memory` 写入节点消费
- **WHEN** 最后一个引用该 output 的写入节点成功完成
- **THEN** 系统 MUST 释放该 output 对应的 typed workflow-managed artifact

#### Scenario: workflow failure discards unreleased managed typed artifacts
- **GIVEN** workflow 运行过程中已产生供 `xlsx_memory` 消费的 typed workflow-managed artifact
- **WHEN** workflow 因失败或取消而结束
- **THEN** 系统 MUST 丢弃尚未释放的 workflow-managed artifacts
- **AND** 系统 MUST NOT 依赖 managed temp dir 清理来完成该能力
