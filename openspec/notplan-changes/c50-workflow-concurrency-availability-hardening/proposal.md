## Why

workflow 并发执行（`ThreadPoolExecutor` / `max_concurrency`）下,共享输出资源（csv/workbook/sheetbook/books）的 joinable get-or-create 目前仍存在更现实的**可用性风险**：

- 当 waiter 在未配置 `max_wait_s` 且 diagnostics 关闭时,会走单次 `Event.wait()` 的无限等待路径（owner 卡死/写锁卡住/外部 I/O 阻塞时会“永久挂起”）。
- 在 Dagster worker/容器场景,这类无限等待会表现为“卡死的 run”,既难定位也难回收,最终变成平台稳定性问题。

此外,写锁当前以 lock file 为主（本地磁盘通常 OK）,但不应默认假设共享盘/NFS/对象存储同样可靠；在这些环境中需要可选择的锁后端与更明确的治理与诊断策略,避免“锁残留/锁不可靠”带来的伪竞态与不可解释失败。

因此需要把“资源等待上限 + 写锁后端/治理”提升为 workflow 的显式、可配置、可测试的 SSOT,并用安全默认值避免生产环境 hang。

## What Changes

- **BREAKING**：workflow 共享资源 joinable get-or-create 的 waiter 等待默认不再允许无限等待；默认启用 `max_wait_s=600`（可配置）,超时 fail-fast 并给出 owner/waiter 诊断信息。
- 新增 workflow 级配置面：
  - `workflow.options.resources_wait`: 控制 inflight join/wait 的 `max_wait_s` 与诊断告警阈值（warn-after / repeat）
  - `workflow.options.write_locks`: 统一控制写锁后端与治理策略（`backend`/`stale_after_s`/`force`）
- 引入新的写锁后端 `mkdir`（用于 NFS/共享盘更稳的原子目录锁）,并允许显式 `backend=none`（由外部协调写入互斥的场景）。
- 文档与测试补齐：
  - workflow YAML 语法与最佳实践（本地盘/NFS/容器）更新
  - 并发/等待/锁冲突的回归测试与可诊断性断言

## Capabilities

### New Capabilities
- `workflow-write-lock-backends`: workflow 共享输出的写锁支持可选后端（file/mkdir/none）,并定义冲突诊断与 stale 治理语义。

### Modified Capabilities
- `workflow-shared-output-containers`: 调整 joinable get-or-create 的超时默认策略（默认 600s）,并要求 timeout 行为可配置且可诊断。
- `yaml-dsl-workflow`: 扩展 workflow YAML 的 `workflow.options`,新增 `resources_wait` 与 `write_locks`,并纳入 schema-only 校验。
- `workflow-ir`: 扩展 `WorkflowOptionsIr`,把上述选项作为编译边界的一部分携带到 runtime。

## Impact

- 受影响代码（SSOT）：`src/scalim/workflow/resources_base.py`、`src/scalim/workflow/resources_*.py`、`src/scalim/workflow/execute.py`、`src/scalim/dsl/by_yaml/workflow_config/*`、`src/scalim/dsl/by_yaml/schema_dsl/*`、`src/scalim/spec/ir/_workflow.py`。
- 受影响测试：workflow 资源并发（join/wait/timeout）、写锁后端（file/mkdir/none）、NFS 风险提示/诊断信息、Dagster/容器“避免 hang”回归。
- 文档与生成物边界（SSOT vs generated）：
  - SSOT 文档：`docs/doc/yaml-dsl/workflow.md`（若涉及 injected blocks,使用 `just gen-docs` 刷新）
  - SSOT schema：`src/scalim/dsl/by_yaml/schema_dsl/builder.py`；生成物 `src/scalim/dsl/by_yaml/schema/workflow.gen.json` 与前端 editor schema（用 `just gen-yaml-dsl-schema` / `just gen-yaml-dsl-editor-schema` 或 `just gen` 刷新）
  - OpenSpec 规范：变更完成后需同步到 `openspec/specs/**/spec.md`,并运行 `just openspec-check` 校验

