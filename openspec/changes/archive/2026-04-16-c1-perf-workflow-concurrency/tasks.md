## 1. workflow 并发 capture+replay 的 loader_call payload 瘦身

- [x] 1.1 定位 workflow 并发进入 capture+replay 的入口与数据流（`src/scalim/workflow/execute.py`、`src/scalim/execution/run_ir.py::run_ir_capture_events`）
- [x] 1.2 在 capture 模式下将 observer 侧 `loader_result_policy` 收敛为 `summary`（避免捕获完整 loader result）
- [x] 1.3 在 capture 模式下将 typed hook 侧 `loader_result_policy` 收敛为 `summary`（避免 hook 捕获完整 loader result）
- [x] 1.4 增加回归测试：workflow `max_concurrency>1` + loader 返回 mapping 时，捕获/回放的 `EVENT_LOADER_CALL.result` 为 summary 结构而非完整 mapping
- [x] 1.5 增加回归测试：workflow 并发下 typed hook `loader_call` 捕获结果为 summary（或等价轻量结构）

## 2. workflow per-run patch 覆盖并发 knobs（parallel_mode/max_workers）

- [x] 2.1 扩展 `WorkflowRunOptionsPatch`：新增 `parallel_mode/max_workers` 字段并补充类型/取值校验（保持 UNSET=inherit 语义）
- [x] 2.2 更新 `run_workflow(..., run_options_patches_by_run_id=...)` 合并逻辑：将 per-run `parallel_mode/max_workers` 覆盖写入 effective `RunOptions`
- [x] 2.3 增加测试：per-run `parallel_mode` 覆盖全局值（`seq` → `adaptive`）
- [x] 2.4 增加测试：per-run `max_workers` 覆盖全局值（`0=auto` → `4`）
- [x] 2.5 增加测试：非法 per-run 值 fail-fast（`parallel_mode` 非法枚举、`max_workers<0`、非 int）

## 3. 规范与验收

- [x] 3.1 将本 change 的 delta specs 同步到主规范（SSOT：`openspec/specs/observer-concurrency-contract/spec.md`、`openspec/specs/workflow-run-patches/spec.md`）
- [x] 3.2 运行 `just openspec-check`（sanitize + validate）确保 OpenSpec 工件一致
- [x] 3.3 运行 `just qa` 确保 lint/tests/drift gates 全部通过
