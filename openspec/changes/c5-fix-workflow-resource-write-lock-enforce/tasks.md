## 1. Publish 写锁生效（核心修复）

- [ ] 1.1 在 `src/scalim/workflow/resources_base.py` 的 `_publish_staged_outputs` 中，根据 staged output 的 `resource_type/resource_id` 判断是否启用写锁，并在 publish 前后调用 `_acquire_write_lock` / `_release_write_lock`
- [ ] 1.2 为 lock owner 写入可诊断字段（workflow_exec_id/resource_type/resource_id/workflow_node_id/staged_path），并确保 `output_staging_keep_on_success` 的 copy-atomic 路径同样受锁保护
- [ ] 1.3 在 publish 异常路径中追加上下文 diff（staged_path/final_path/keep_on_success 等），确保错误可定位且锁一定释放

## 2. 行为与错误契约

- [ ] 2.1 当 `write_lock=true` 且存在并发 writer 时，publish MUST fail-fast（复用 `ScalimWorkflowWriteError`），并包含 `lock_path` 与可读的 `lock_owner.*` 信息
- [ ] 2.2 当 `write_lock=false` 时，不得因 lock 冲突 fail-fast（保持默认“允许覆盖”的历史行为）

## 3. 测试

- [ ] 3.1 在 `tests/workflow/test_workflow_resources_coverage.py` 增加 workbook 的并发 publish 用例：`write_lock=True` 时断言其中一个 publish 抛出 `ScalimWorkflowWriteError`
- [ ] 3.2 增加 sheetbook export 的并发 publish 用例：`export_write_lock=True` 时同样断言冲突 fail-fast
- [ ] 3.3 增加 `write_lock=False` 的对照用例：两次 publish 均可完成，最终文件允许被最后一次覆盖（不做锁冲突断言）

## 4. 规范/文档与验收门禁

- [ ] 4.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/yaml-dsl-books-resources/spec.md`（或新增更合适的 workflow publish 语义 spec），并运行 `just openspec-check` 验证 OpenSpec 工件一致性
- [ ] 4.2 若触及任何 `*.gen.*` 或 `BEGIN/END AUTOGEN:*` 注入区块：仅修改其 SSOT，并用 `just gen-docs` 重新生成（禁止手改生成物/注入区块内部）
- [ ] 4.3 跑 `just qa` 作为最终验收：测试通过 + lint/格式化通过 + 漂移检查通过
