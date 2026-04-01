## Why

workflow 并发执行（`ThreadPoolExecutor` / `max_concurrency`）下,当前更现实的**可用性风险**主要来自带 joinable inflight 路径的共享资源创建：

- 目前 `workbook/csv` 的 waiter 在未配置 `max_wait_s` 且 diagnostics 关闭时,会走单次 `Event.wait()` 的无限等待路径（owner 卡死/写锁卡住/外部 I/O 阻塞时会“永久挂起”）。
- 在 Dagster worker/容器场景,这类无限等待会表现为“卡死的 run”,既难定位也难回收,最终变成平台稳定性问题。

因此需要把“资源等待上限 + 等待诊断”提升为 workflow 的显式、可配置、可测试的 SSOT,并用安全默认值避免生产环境 hang。

NOTE: 写锁/输出 staging 的策略收敛在另一个变更中处理(本 change 仅聚焦 join/wait 可用性硬化)。

## What Changes

- **BREAKING**：workflow 共享资源 joinable get-or-create 的 waiter 等待默认不再允许无限等待；默认启用 `max_wait_s=600`（可配置）,超时 fail-fast 并给出 owner/waiter 诊断信息。
- 新增 workflow 级配置面：
  - `workflow.options.resources_wait`: 控制 inflight join/wait 的 `max_wait_s` 与诊断告警(`diagnostics.enabled/warn_after_s/repeat_every_s/capture_owner_callsite`)
- 文档与测试补齐：
  - workflow YAML 语法与最佳实践（本地盘/NFS/容器）更新
  - 并发/等待/超时的回归测试与可诊断性断言

## Capabilities

### Modified Capabilities
- `workflow-shared-output-containers`: 调整 joinable get-or-create 的超时默认策略（默认 600s）,并要求 timeout 行为可配置且可诊断。
- `yaml-dsl-workflow`: 扩展 workflow YAML 的 `workflow.options`,新增 `resources_wait`,并纳入 schema-only 校验。
- `workflow-ir`: 扩展 `WorkflowOptionsIr`,把 `resources_wait` 作为编译边界的一部分携带到 runtime。

## Impact

- 受影响代码（SSOT）：`src/scalim/workflow/resources_base.py`、`src/scalim/workflow/resources_*.py`、`src/scalim/workflow/execute.py`、`src/scalim/dsl/by_yaml/workflow_config/*`、`src/scalim/dsl/by_yaml/schema_dsl/*`、`src/scalim/spec/ir/_workflow.py`。
- 受影响测试：workflow 资源并发（join/wait/timeout）、等待诊断信息、Dagster/容器“避免 hang”回归。
- 实施前置：需先确认 joinable wait 的真实覆盖范围,再生成 design/spec/tasks。
- 文档与生成物边界（SSOT vs generated）：
  - SSOT 文档：`docs/doc/yaml-dsl/workflow.md`（若涉及 injected blocks,使用 `just gen-docs` 刷新）
  - SSOT schema：`src/scalim/dsl/by_yaml/schema_dsl/builder.py`；生成物 `src/scalim/dsl/by_yaml/schema/workflow.gen.json`（用 `just gen-yaml-dsl-schema` 或 `just gen` 刷新）
  - OpenSpec 规范：变更完成后需同步到 `openspec/specs/**/spec.md`,并运行 `just openspec-check` 校验
