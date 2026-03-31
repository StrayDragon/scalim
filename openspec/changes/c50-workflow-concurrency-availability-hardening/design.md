## Context

workflow 并发执行（`ThreadPoolExecutor` / `max_concurrency`）下,共享输出资源的 joinable get-or-create 目前存在主要的可用性风险：当 owner 线程卡死/外部 I/O 阻塞/写锁卡住时,waiter 可能进入无限等待。

当前实现（`src/scalim/workflow/resources_base.py`）已经具备:

- joinable inflight 机制（owner 创建,waiter join）
- 可选 wait diagnostics（warn-after / repeat）
- 可选 max_wait_s（超时 fail-fast）,但默认 `max_wait_s=None` 且 diagnostics 关闭时走单次 `Event.wait()` 的无限等待快路径
- 基于 lock file 的写锁 owner/stale/force reclaim 能力,但仍停留在资源层参数,缺少 workflow 级 SSOT 与可测试的默认策略

在 Dagster worker/容器场景,无限等待会表现为 run 永久挂起,难定位难回收,最终成为平台稳定性问题。
因此需要把“资源等待上限 + 写锁后端/治理”提升到 workflow 的显式配置面,并给出安全默认值与可诊断输出。

约束:

- 运行时需兼容 Python 3.6
- 不应默认假设共享盘/NFS/object storage 的 file lock 语义可靠；需要提供更稳的后端选择
- 文档与 schema 为用户侧 SSOT,且必须可通过 drift gate 验收

## Goals / Non-Goals

**Goals:**

- BREAKING: 默认不再允许无限等待; joinable waiter 默认 `max_wait_s=600` 超时 fail-fast,错误包含 owner/waiter 诊断信息。
- 新增 workflow YAML 配置 `workflow.options.resources_wait` 与 `workflow.options.write_locks`,并纳入 schema-only 校验与 IR 编译边界。
- 新增写锁后端 `mkdir`（原子目录锁,更适合 NFS/共享盘），并支持 `backend=none`（外部已协调互斥的场景）。
- 补齐并发/等待/锁冲突的回归测试与 docs 最佳实践（本地盘/NFS/容器）。

**Non-Goals:**

- 不引入分布式锁服务（Redis/DB 等）作为默认后端。
- 不保证所有共享存储的强一致锁语义;仅提供可选后端 + 风险提示 + fail-fast。
- 不在 v1 一次性重写所有资源实现细节;聚焦 workflow 层 SSOT 与可用性硬化。

## Decisions

1) **Default timeout policy**

- 将 joinable waiter 的默认 `max_wait_s` 收敛为 600 秒:
  - 未配置时即启用 fail-fast（避免 hang）
  - 允许通过 `workflow.options.resources_wait.max_wait_s` 覆盖（更小用于测试/更大用于离线任务）
- 为减少误用,不再把“无限等待”作为默认或推荐配置；若需要,应通过显式配置选择很大的值并承担风险。

2) **Wait diagnostics as workflow-level SSOT**

- wait diagnostics 与 timeout 都由 `workflow.options.resources_wait` 统一配置,并从 YAML → IR → runtime 贯穿:
  - `warn_after_s` / `repeat_every_s`
  - 可选 `capture_owner_callsite`（仅诊断用途）

3) **Write lock policy SSOT**

- 写锁后端与治理由 `workflow.options.write_locks` 统一控制:
  - `backend`: `file|mkdir|none`
  - `stale_after_s` + `force`（治理 stale lock）
- 资源层不得再隐式决定锁策略；需要在 runtime manager 构造时注入统一 policy。

4) **Docs / Generated boundaries & drift gates**

- workflow YAML 文档 SSOT：`docs/doc/yaml-dsl/workflow.md`（若涉及 injected blocks,用 `just gen-docs`）
- workflow schema SSOT：`src/scalim/dsl/by_yaml/schema_dsl/**`；生成物：`src/scalim/dsl/by_yaml/schema/workflow.gen.json`（用 `just gen-yaml-dsl-schema`/`just gen`）
- OpenSpec 工件提交前必须通过 `just openspec-check`；实现期通过 `just qa` 兜底 drift。

## Risks / Trade-offs

- [破坏性默认变更] 生产上可能从“挂起”变为“超时失败” → 缓解:
  - 错误消息必须包含 resource_id/owner/wait_s/max_wait_s 以及治理 hint
  - docs 提供推荐配置与排障路径
- [NFS file lock 不可靠] `O_EXCL`/unlink 语义可能异常 → 缓解:
  - 提供 `mkdir` 后端作为更稳的原子锁
  - 明确 `backend=none` 的风险与适用场景
- [诊断/轮询开销] 由单次 wait 转为轮询等待 → 缓解:
  - 轮询间隔基于 warn/timeout 自动取最小;保持默认 1s 级别
  - 仅在 inflight wait 路径引入,不影响无并发场景

## Migration Plan

- 先在 schema + config parsing + IR 层引入新的 options,并确保 runtime manager 能消费。
- 再调整默认 timeout 并补齐回归测试,确保 hang 变为可诊断的 fail-fast。
- 对 legacy `resources.*.write_lock` 入口进行调研后,收敛为单一路径:
  - 若保留,必须有明确冲突规则与 fail-fast
  - 若移除,必须给出迁移提示与 docs 更新

## Open Questions

- legacy `write_lock` 的最终迁移策略: 直接移除还是保留但要求与 workflow.options 一致?
- 默认 `warn_after_s`/repeat 策略是否需要在没有显式开启 diagnostics 时仍对超时场景输出一次性提示?
