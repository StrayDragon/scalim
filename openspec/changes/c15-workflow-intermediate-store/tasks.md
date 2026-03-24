## 1. Define the in-memory output contract

- [ ] 1.1 新增 workflow-managed CSV 的内存 artifact / sink 契约，并确保其字符串化语义与现有 CSV 中间文件一致
- [ ] 1.2 扩展 execution 输出装配与 `ExecutionResult`，让 workflow 托管的 pathless CSV target 能返回内存结果而不是临时路径

## 2. Integrate workflow-managed outputs

- [ ] 2.1 将 workflow 对 pathless CSV 的托管方式从“output path override + managed temp dir”改为“显式 workflow-managed output allowlist + 内存 artifact 发布”
- [ ] 2.2 为 workflow 运行时增加 `(producer_node_id, output_id)` 级别的 write-consumer 计数与最终释放逻辑

## 3. Update write-node resource consumption

- [ ] 3.1 改造 workflow shared resource 写入路径，使 csv/workbook/sheetbook 能同时消费文件路径 output 与内存 CSV artifact
- [ ] 3.2 保持字段对齐、header_policy、commit/discard 与事件归因语义不漂移

## 4. Verify behavior and SSOT

- [ ] 4.1 更新 workflow 相关测试与 demo fixtures，验证 pathless CSV + writes 不再依赖 managed temp outputs 目录且结果保持一致
- [ ] 4.2 同步 OpenSpec 主规范 SSOT（`openspec/specs/**/spec.md`）与本 change delta 对齐，并通过 `just openspec-check`
