# workflow-sheetbook-resources Specification

## ADDED Requirements

### Requirement: sheetbook plan creation MUST be atomic within a workflow exec
当 workflow 并发执行多个 nodes 且多个 write intents 引用同一个 `sheetbook` 资源时,系统 MUST 确保该 sheetbook 在一次 workflow 执行内仅创建一个 plan,并且不得发生并发覆盖导致的丢写：

- 对同一 `sheetbook_id` 的 “get-or-create” MUST 原子（并发首次命中不得产生多个 plan）。
- 并发写入 MUST 汇聚到同一个 plan,最终导出/commit MUST 包含所有写入结果（不得丢写）。

#### Scenario: concurrent writes to a sheetbook do not lose data
- **GIVEN** workflow 并发执行两个 nodes A/B
- **AND** A 写入 sheetbook `report` 的 sheet `s1`
- **AND** B 写入 sheetbook `report` 的 sheet `s2`
- **WHEN** 多次执行该 workflow
- **THEN** 导出的 sheetbook（内存或 xlsx）MUST 同时包含 `s1` 与 `s2` 的内容

