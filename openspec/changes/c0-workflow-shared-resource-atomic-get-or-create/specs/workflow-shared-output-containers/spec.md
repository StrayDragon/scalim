# workflow-shared-output-containers Specification

## ADDED Requirements

### Requirement: shared resource plan creation MUST be atomic and joinable within a workflow exec
当 workflow 并发执行多个 nodes 且多个 write intents 引用同一个共享资源（`csv` 或 `workbook`）时,系统 MUST 确保该资源在一次 workflow 执行内仅创建一个 plan,并允许并发写入方 join 到同一 plan：

- 对同一 `resource_id` 的 “get-or-create” MUST 原子（并发首次命中不得产生多个 plan）。
- `csv/workbook` 的写锁获取 MUST 与该 plan 绑定且在一次 workflow 执行内只发生一次；同一 workflow 内的其它并发写入 MUST join 而不是被误判为并发写者。
- 最终 commit MUST 包含所有写入方产生的写入意图（不得丢写）。

#### Scenario: concurrent writes to a shared workbook join a single plan
- **GIVEN** workflow 并发执行两个 nodes A/B
- **AND** A 与 B 都写入同一个共享 workbook 资源 `report` 的不同 sheets
- **WHEN** 多次执行该 workflow
- **THEN** 系统 MUST 不得因“重复获取写锁”而 fail-fast
- **AND** 最终导出的 workbook MUST 同时包含 A 与 B 的写入结果

#### Scenario: concurrent appends to a shared csv join a single plan
- **GIVEN** workflow 并发执行两个 nodes A/B
- **AND** A 与 B 都 append 写入同一个共享 csv 资源 `detail`
- **WHEN** 多次执行该 workflow
- **THEN** 系统 MUST 不得因“并发首次命中同一 csv”而 fail-fast
- **AND** 最终落盘的 csv MUST 包含两段 append 的写入结果（顺序由声明顺序决定）

