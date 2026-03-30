## Context

workflow runtime 当前采用 `ThreadPoolExecutor` 并发调度 runs,调度队列/状态机由主线程推进；核心共享结构（例如 ctx store / artifacts store / shared resources manager）在实现侧基本都有锁保护。

更现实的风险在于“等待型逻辑”与“跨进程写入互斥”：

- 共享资源 joinable get-or-create 的 waiter 在 `max_wait_s` 未设置且 diagnostics 关闭时会无限等待（owner 卡死/写锁卡住/外部 I/O 卡住会导致 workflow run 挂死）。
- 写锁当前以 lock file（`O_EXCL` 创建）为主,在本地磁盘通常可靠；但对共享盘/NFS/对象存储不应默认假设同样可靠,需要提供明确的后端选择与风险提示。

同时,仓库测试默认开启 xdist 并发（`-n auto`）,任何依赖 wall-clock `sleep`/极小 timeout 的测试都更容易在 CI 抖动；设计上需要把等待/超时测试写成 monotonic + 明确完成信号的方式。

## Goals / Non-Goals

**Goals:**
- workflow 共享资源 joinable 等待默认可控：不允许无限等待,默认 `max_wait_s=600` 超时 fail-fast 且可诊断。
- 明确并提供 workflow 级配置面（YAML + IR）用于资源等待与写锁治理,避免散落在环境变量/全局常量里。
- 写锁支持多后端（至少 `file` 与 `mkdir`）,并提供可控的 stale/force 治理（默认关闭）。
- 保持 Python 3.6 运行时兼容,不引入新的强依赖。

**Non-Goals:**
- 不在本变更中重构/拆分 `execute.py` 或 `compiler.py` 的体量问题（作为独立可维护性变更推进）。
- 不引入分布式锁服务（如 Redis/etcd）或“对象存储级锁”能力；仅提供 best-effort 后端与明确风险提示。

## Decisions

### 1) 资源等待：默认有限超时 + monotonic 计时

- 默认策略：workflow 共享资源 joinable wait MUST 有上限；默认 `max_wait_s=600`。
- 计时基准：使用 `time.monotonic()` 计算 `wait_s`,避免 wall clock 调整导致的误判。
- 配置入口：新增 `workflow.options.resources_wait`（YAML）并编译到 `WorkflowOptionsIr`（IR）,由 runtime 注入到 `WorkflowResourceManagerBase(max_wait_s=...)`。
- diagnostics：保留可选的 warn-after/repeat（默认关闭）,用于定位“慢/卡住的 owner”。

### 2) 写锁：后端可选（file/mkdir/none）+ 明确治理边界

- 新增写锁后端枚举 `backend`：
  - `file`：保留现有 `.scalim.lock` 文件锁实现（本地盘优先）。
  - `mkdir`：使用原子 `mkdir` 的目录锁（建议用于 NFS/共享盘）,锁目录形态与 owner 信息存储需要标准化。
  - `none`：显式关闭写锁（由外部系统保证互斥/或输出路径隔离的场景）。
- 治理策略：`stale_after_s + force` 仅在显式配置时启用；且 force MUST 以“锁 age >= stale_after_s”为前置条件,禁止默认删除新鲜锁。
- 配置入口：新增 `workflow.options.write_locks` 并编译到 IR,由资源模块统一消费；避免每个资源类型各自实现不同的锁策略。

### 3) DSL/Schema/Docs 的 drift gate（SSOT vs generated）

- SSOT（解析与类型）：`src/scalim/dsl/by_yaml/workflow_config/_models.py` 与 `src/scalim/dsl/by_yaml/workflow_config/_parse.py`。
- SSOT（schema 定义）：`src/scalim/dsl/by_yaml/schema_dsl/builder.py`。
- 生成物：
  - `src/scalim/dsl/by_yaml/schema/workflow.gen.json` 由 `just gen-yaml-dsl-schema`（或 `just gen`）刷新。
  - 文档站点生成与 injected blocks 由 `just gen-docs` 刷新。
- 规范校验：在共享/归档前运行 `just openspec-check`（sanitize + `openspec validate --all --strict --no-interactive`）。

## Risks / Trade-offs

- [行为变化] 默认超时会把“永久 hang”变为 fail-fast：→ 提供显式配置项允许调大阈值,并在错误中输出 owner/age/callsite 等诊断信息。
- [NFS 语义] `mkdir` 不保证所有共享存储都可靠：→ 文档明确“不要默认假设共享盘/对象存储锁可靠”,并提供 `backend=none` 作为外部协调兜底。
- [误删锁] stale/force 若滥用可能删掉仍在运行的 writer：→ 要求 `stale_after_s` + age 判定,并在诊断 diff 中包含 owner 信息与 lock_age。
- [测试抖动] timeout 类测试易 flaky：→ 用 monotonic + 明确完成信号（事件/Barrier）替代 `sleep` 驱动。

## Migration Plan

1) 先更新 OpenSpec delta specs（本 change）并通过 `just openspec-check`。
2) 实施顺序：YAML options → IR → runtime wiring → lock backend → tests → docs + 生成物刷新。
3) 回滚策略：若生产出现误报,可先将默认 `max_wait_s` 提升到更保守值并发布；必要时 revert 该变更。

## Open Questions

- server/web API 场景下,是否需要提供“输出路径随机后缀/隔离”能力以允许同一 workflow 并发多次写到逻辑同名目标？若需要,更适合做成 entrypoint 侧的 opt-in override 还是 YAML authoring surface？
