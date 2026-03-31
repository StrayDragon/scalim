## 1. Review Gate (Maintainer)

- [ ] 1.1 维护者确认 BREAKING 行为：共享资源 joinable waiter 默认 `max_wait_s=600` 且不再允许无限等待作为默认策略
- [ ] 1.2 维护者确认写锁后端策略：`file|mkdir|none` 的语义与适用场景（本地盘/NFS/外部协调）

## 2. YAML Schema & Config Parsing (SSOT)

- [ ] 2.1 扩展 workflow YAML schema: 新增 `workflow.options.resources_wait` 与 `workflow.options.write_locks`（SSOT: `src/scalim/dsl/by_yaml/schema_dsl/**`）
- [ ] 2.2 运行 `just gen-yaml-dsl-schema`(或 `just gen`) 刷新 `src/scalim/dsl/by_yaml/schema/workflow.gen.json`（生成物禁止手改）
- [ ] 2.3 更新 workflow YAML 解析/类型: 将新 options 解析为结构化对象并做 fail-fast 校验（保持 Python 3.6 兼容）

## 3. IR Boundary

- [ ] 3.1 扩展 `WorkflowOptionsIr`：携带 `resources_wait` 与 `write_locks` 进入 runtime（SSOT: `src/scalim/spec/ir/_workflow.py` 或等价）
- [ ] 3.2 确认 YAML → IR → runtime 的传递链路可测且不依赖线程调度（回归测试覆盖）

## 4. Runtime: Wait Hardening (Availability)

- [ ] 4.1 将共享资源 manager 的默认 `max_wait_s` 收敛为 600s（未配置时启用 fail-fast）
- [ ] 4.2 超时错误 MUST 包含 resource_id/owner_thread/wait_s/max_wait_s 与治理 hint；并在 diagnostics 开启时可选包含 owner callsite
- [ ] 4.3 `commit_all()/discard_all()` 的 drain 等待 MUST 复用同一 resources_wait 策略（warn-after/timeout）

## 5. Runtime: Write Lock Backends

- [ ] 5.1 引入写锁后端 `mkdir`（原子目录锁）与 `none`（禁用写锁），并保持 `file` 后端语义不回退
- [ ] 5.2 实现 stale 治理：`stale_after_s` + `force` 的回收/重试策略与可诊断错误 diff
- [ ] 5.3 明确 legacy `resources.*.write_lock` 与新 `workflow.options.write_locks` 的冲突规则与迁移策略（优先 fail-fast + 文档提示）

## 6. Tests / Docs / Gates

- [ ] 6.1 新增回归测试：并发 join/wait 在默认策略下不会无限 hang（超时后 fail-fast 且含诊断）
- [ ] 6.2 新增回归测试：`file|mkdir|none` 后端的锁冲突/回收语义
- [ ] 6.3 更新 docs：`docs/doc/yaml-dsl/workflow.md` 补充 resources_wait/write_locks 最佳实践（若涉及 injected blocks,用 `just gen-docs`）
- [ ] 6.4 运行 `just openspec-check` 确保 OpenSpec 工件一致性
- [ ] 6.5 运行 `just qa` 通过 lint/tests + drift checks
