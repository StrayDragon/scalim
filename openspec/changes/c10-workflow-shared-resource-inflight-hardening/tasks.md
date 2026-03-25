## 1. 基础设施

- [ ] 1.1 在 `src/scalim/workflow/resources_base.py` 中引入 `WorkflowResourceWaitDiagnostics` dataclass（对齐 `PreloadCacheWaitDiagnostics` 接口: `enabled`/`warn_after_s`/`repeat_every_s`/`capture_owner_callsite`）
- [ ] 1.2 `_WorkflowResourceManagerBase.__init__` 接收 `wait_diagnostics` 参数,默认 `enabled=False`
- [ ] 1.3 引入 `_compute_poll_interval_s` 辅助函数（可复用 PreloadCache 同名函数的逻辑）

## 2. joinable get-or-create 等待诊断

- [ ] 2.1 改造 `_get_or_create_joinable_plan` 的 waiter 路径: `inflight_state.done.wait()` → poll loop + diagnostics
- [ ] 2.2 超过 `warn_after_s` 时 emit 告警（包含 resource_id/resource_type/owner_thread/waiter_thread/wait_s）
- [ ] 2.3 支持 `repeat_every_s` 重复告警
- [ ] 2.4 支持可选 `capture_owner_callsite`（记录 owner 创建时的调用栈）

## 3. 可选超时

- [ ] 3.1 引入 `max_wait_s: Optional[float]` 参数（None = 不超时）
- [ ] 3.2 超时后以 `WorkflowWriteError` 失败,包含诊断信息
- [ ] 3.3 确保超时不影响 owner 线程的创建流程（owner 继续执行,仅 waiter 失败）

## 4. commit/discard 并发交错（drain 策略）

- [ ] 4.1 `commit_all()` 在 commit 前等待所有 `_inflight_workbooks`/`_inflight_csvs` 完成
- [ ] 4.2 `discard_all()` 同样等待 inflight 完成后再 discard
- [ ] 4.3 drain 等待复用 wait diagnostics 配置（warn-after/timeout）

## 5. 测试

- [ ] 5.1 单元测试: waiter 等待超过阈值时产生告警
- [ ] 5.2 单元测试: max_wait_s 超时后 WorkflowWriteError
- [ ] 5.3 隔离测试: commit_all 与 inflight 并发交错时 drain 正确等待（使用 monkeypatch 控制 owner 卡住）
- [ ] 5.4 确认默认 `enabled=False` 时无行为变化

## 6. 规范同步

- [ ] 6.1 delta spec 同步到 `openspec/specs/workflow-shared-output-containers/spec.md`
- [ ] 6.2 `just qa` 通过
