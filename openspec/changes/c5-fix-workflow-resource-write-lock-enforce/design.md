## Context

- workflow 资源输出采用 staging → publish 两阶段：各资源先写入 staging，workflow 结束统一 publish 到 `final_path`（原子 replace/copy-atomic）。
- 当前 publish 阶段（`_WorkflowResourceManagerBase._publish_staged_outputs`）未使用已有写锁：并发 workflow 进程写同一 `final_path` 时出现“最后写入者胜”，且 `write_lock` 配置形同虚设。
- 仓库已有跨进程写锁实现（基于 `<final_path>.scalim.lock` 的 lockfile），并且解析层已把 workbook/sheetbook 的 `write_lock` 解析并传入 resource manager，但 publish 未消费。

约束与治理：

- 运行时需保持 Python 3.6 兼容。
- 不直接手工编辑任何 `*.gen.*` 生成物或 `BEGIN/END AUTOGEN:*` 注入区块；如本修复触及文档/规范漂移，按 SSOT + generator 方式处理（优先 `just gen-docs`），并用 `just qa`/`just openspec-check` 兜底漂移门禁。

## Goals / Non-Goals

**Goals:**

- 当资源配置 `write_lock=true` 时，publish 阶段 MUST 在 `final_path` 上互斥：
  - 并发 writer 出现时 fail-fast，给出可操作的错误（包含 `lock_path` 与 owner 信息）。
- 保持 staging + 原子 replace/copy-atomic 的语义不变（不引入“半写”）。
- 默认行为不变：`write_lock=false` 时仍允许并发 publish（可能覆盖，属于显式选择）。
- 锁持有时间尽量短：只覆盖“最终影响 `final_path` 的那一步”。

**Non-Goals:**

- 不在计算/写入 staging 阶段持锁（避免长时间占锁与扩大失败面）。
- 不引入“等待/排队串行化发布”的阻塞策略（本次仅 fail-fast）。
- 不为 CSV 等未暴露 `write_lock` 配置的资源新增锁语义（后续如需再开 change）。

## Decisions

### 1) 在 publish 边界获取/释放写锁（核心）

在 `_WorkflowResourceManagerBase._publish_staged_outputs` 中，对每个 staged output：

- 若该 output 对应资源启用了 `write_lock`，则：
  - `lock_path = _acquire_write_lock(final_path, owner=...)`
  - 执行 publish（`replace` 或 `_copy_file_atomic`）
  - `finally: _release_write_lock(lock_path)`

锁作用域覆盖 publish 的两种路径：

- `Path(staged_path).replace(final_path)`（默认）
- `self._copy_file_atomic(staged_path, final_path=final_path)`（`output_staging_keep_on_success=true`）

### 2) 如何判断某个 staged output 是否需要锁

基于 staged output 的 `resource_type/resource_id`，在 manager 内部做最小映射：

- `resource_type == "workbook"`：读取 `self._workbook_write_lock[resource_id]`（legacy `workbook` 默认 `True`；`books.kind=xlsx_file` 由 YAML `write_lock` 决定）
- `resource_type == "sheetbook"`：读取 `self._sheetbook_defs[resource_id].export_write_lock`（legacy `sheetbook` 与 `books.kind=xlsx_memory.export_xlsx` 统一）
- `resource_type == "csv"`：本次不加锁（行为保持）

### 3) 冲突行为与错误信息

- 复用现有 `_acquire_write_lock` 的 fail-fast 语义：当 lockfile 已存在时抛出 `ScalimWorkflowWriteError`，并在 `diff` 中包含：
  - `lock_path`、`lock_age_s`（如可得）、`lock_owner.*`（如可读）
  - `hint=delete_lock_file_if_safe:<lock_path>`
- publish 侧在捕获异常时追加 publish 上下文到 `diff`（resource_type/id、staged_path、final_path、keep_on_success 等），便于定位。

### 4) lock owner 元信息

调用 `_acquire_write_lock(..., owner=...)` 时写入至少以下字段，方便排障与审计：

- `workflow_exec_id`
- `resource_type`
- `resource_id`
- `workflow_node_id`
- `staged_path`

## Risks / Trade-offs

- `write_lock=true` 的用户将从“静默覆盖”变为“冲突时报错”；这是修复承诺行为，但可能暴露既有并发写配置问题。
- lockfile 位于 `final_path` 同目录，若目录权限不足会导致 publish fail-fast；符合用户显式开启锁的预期（需要可写目录才能实现互斥）。
- 进程异常退出可能遗留 lockfile；当前策略不做自动 force/stale 清理，依赖错误提示引导人工处理（后续可另开 change 引入 `stale_after_s/force` 策略）。

## Migration Plan

- 默认（`write_lock=false`）无行为变化，无迁移。
- 已启用 `write_lock=true` 的场景：若出现并发冲突，需要调整调度/输出路径确保同一 `final_path` 不被并发写入，或显式关闭 `write_lock` 退回“允许覆盖”的旧行为。

## Open Questions

- 无（本次以 publish 边界 fail-fast 为确定策略；如需“等待/串行化”或扩展到 CSV 等资源，另开 change）。
