## 1. Review Gate (Maintainer)

- [x] 1.1 维护者确认 BREAKING 行为：共享资源 joinable waiter 默认 `max_wait_s=600` 且不再允许无限等待作为默认策略

## 2. YAML Schema & Config Parsing (SSOT)

- [x] 2.1 扩展 workflow YAML schema: 新增 `workflow.options.resources_wait`（含 diagnostics.*；SSOT: `src/scalim/dsl/by_yaml/schema_dsl/**`）
- [x] 2.2 运行 `just gen-yaml-dsl-schema`(或 `just gen`) 刷新 `src/scalim/dsl/by_yaml/schema/workflow.gen.json`（生成物禁止手改）
- [x] 2.3 更新 workflow YAML 解析/类型: 将 `resources_wait` 解析为结构化对象并做 fail-fast 校验（保持 Python 3.6 兼容）

## 3. IR Boundary

- [x] 3.1 扩展 `WorkflowOptionsIr`：携带 `resources_wait` 进入 runtime（SSOT: `src/scalim/spec/ir/_workflow.py` 或等价）
- [x] 3.2 确认 YAML → IR → runtime 的传递链路可测且不依赖线程调度（回归测试覆盖）

## 4. Runtime: Wait Hardening (Availability)

- [x] 4.1 将共享资源 manager 的默认 `max_wait_s` 收敛为 600s（未配置时启用 fail-fast）
- [x] 4.2 超时错误 MUST 包含 resource_id/owner_thread/wait_s/max_wait_s 与治理 hint；并在 diagnostics 开启时可选包含 owner callsite
- [x] 4.3 `commit_all()/discard_all()` 的 drain 等待 MUST 复用同一 resources_wait 策略（warn-after/timeout）

## 5. Tests / Docs / Gates

- [x] 5.1 新增回归测试：并发 join/wait 在默认策略下不会无限 hang（超时后 fail-fast 且含诊断）
- [x] 5.2 更新 docs：`docs/doc/yaml-dsl/workflow.md` 补充 resources_wait 最佳实践（若涉及 injected blocks,用 `just gen-docs`）
- [x] 5.3 运行 `just openspec-check` 确保 OpenSpec 工件一致性
- [x] 5.4 运行 `just qa` 通过 lint/tests + drift checks
