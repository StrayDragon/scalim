## Context

当前 `workflow` / `sinks` 的并发安全主要靠两类“锁”兜底：

- **进程内锁**：`workflow` 执行期的共享可变状态（`artifacts/ctx/resources` 等）通过 `threading.Lock` + joinable get-or-create 的方式实现互斥/等待/诊断。
- **跨进程锁**：围绕最终输出路径创建 `<final_path>.scalim.lock` 文件来 fail-fast（`workflow/resources_base.py` 与 `sinks/_internal/*`）。

这套方案在单机脚本场景能工作，但在“服务端多请求并发”的场景会带来明显负担：

- **锁冲突**：不同请求写同一路径时要么互斥等待，要么 fail-fast；两者都会放大尾延迟与运维复杂度。
- **目录污染**：在用户产物路径旁生成 `.scalim.lock` 等文件（以及失败时的残留）会影响可维护性与用户体验。
- **推理成本高**：joinable/timeout/diagnostics/force stale 等逻辑让实现难以局部推断，重构与演进成本高。

本变更希望用“**单写者（actor/controller）+ 版本化输出（D-2）**”从根上减少共享可变状态与跨进程互斥的需求。

约束：

- `src/scalim/` 运行时必须兼容 **Python 3.6**。
- 不手工修改任何 `*.gen.*` 与 injected blocks（见 repo doc governance 规则）。

## Goals / Non-Goals

**Goals:**

- 引入 **版本化输出（D-2）**：用户配置的输出 `path` 自动处理用户的路径, 如果给出的是文件路径则获取文件路径同级路径并创建独一无二的目录, 如果是一个目录路径则同时创建和默认输出配置, 语义升级为“目录 root”；每次运行写入独立版本目录；通过 `manifest/latest.json` 指向当前版本。
- 版本化输出写入前 MUST 自动创建 root 及其父目录（`mkdir(parents=True, exist_ok=True)`），并只在 root 下创建框架自管目录（`versions/`、`manifest/`）。
- 框架 **不再在用户产物路径旁生成** `<file>.scalim.lock` 写锁文件；跨进程并发通过“版本隔离”天然消解。
- `workflow` 并发执行路径（组 B）采用 **单写者** 模式：共享状态只允许由 controller 更新；并发线程只做计算与结果回传。
- 保留 staging → publish 的原子性，且在 publish 完成后原子更新 latest 指示（last-writer-wins，但不丢历史版本）。

**Non-Goals:**

- 不引入跨主机/跨文件系统的分布式一致性（例如基于 DB/etcd 的强一致“latest”）。
- 不在本变更内实现自动清理/GC（保留所有版本；后续可加 retention/prune 能力）。
- 不追求全仓库“彻底无锁”（缓存、第三方库 IO 等处的锁可保留）；本变更优先覆盖组 B/D 的关键路径。

## Decisions

### Decision 1: 选择 D-2（版本化输出 + manifest/latest 指示）

将“最终输出路径”的概念升级为“**输出 root 目录**”，并按 run 生成版本化目录：

- 用户配置：`path` 为目录（output root）。
- 每次运行生成一个 `version_id`：
  - workflow: `version_id` MUST 等于 `workflow_exec_id`
  - standalone demand: `version_id` MUST 等于 `run_id`
- `version_id` MUST 是安全的路径段（不得包含路径分隔符、`..` 等；默认生成的 `workflow_exec_id/run_id` 满足该约束）。
- 运行产物落在：`<root>/versions/<version_id>/...`
- latest 指示落在：`<root>/manifest/latest.json`（原子 replace）

这样，多进程并发写同一个 `<root>` 时不会争抢同一最终文件路径，因此无需 `<final>.scalim.lock`。

备选方案与取舍：

- **继续使用 lockfile**：仍会产生目录污染与锁冲突；在服务端多并发请求下风险更高。
- **单文件“latest 直接覆盖”**：不保留历史版本，难以回溯诊断；并发覆盖不可控。
- **symlink latest**：跨平台/权限/打包分发复杂；JSON 指示更通用、可扩展。

### Decision 2: 输出 root 的目录布局（框架自管目录边界）

为避免“到处散落元数据/锁文件”，约定输出 root 下仅创建/写入以下自管目录：

- `<root>/versions/`：版本目录集合（用户真正关心的产物在这里）
- `<root>/manifest/`：框架元数据（latest 指示等）

除上述目录外，框架 MUST NOT 在 `<root>` 的其它位置创建 `.scalim.lock` 等文件。

同时，root 本身就是隔离域（namespace boundary）：

- v1 不引入 `tenant/namespace` 维度的 `latest` 指示（不生成 `latest.<tenant>.json` 之类的变体）。
- 服务端多租户场景 MUST 通过目录分层为每个租户/业务提供独立 root。

### Decision 3: 版本目录内的命名规则（稳定、可预测）

在 `<root>/versions/<version_id>/` 内，按资源类型组织：

- Books（`resources.books.*`）：`books/<book_id>.xlsx`
- Files（`resources.files.*`）：`files/<file_id>.csv`

命名规则以 `<book_id>/<file_id>` 为 SSOT，避免需要额外的“用户自定义文件名”字段（后续如确有需求再扩展）。

### Decision 4: latest 指示与版本 manifest（原子性与可诊断性）

为兼顾可诊断性与 latest 文件稳定：

- 每个版本在其目录内写入：`<root>/versions/<version_id>/manifest.json`
  - 内容包含：`version_id`、创建时间、产物相对路径（books/files）、以及可选的执行元信息（如 workflow_id）。
- root 下写入：`<root>/manifest/latest.json`
  - 内容至少包含：`version_id` 与 `version_manifest_relpath`（例如 `versions/<version_id>/manifest.json`）

原子性：

- `latest.json` 通过 “写临时文件 + atomic replace” 更新，保证并发下文件不会被写坏（JSON 总是完整）。
- `latest.json` 语义为 **last-writer-wins**；但历史版本目录永远保留，因此不会丢数据。

### Decision 5: 组 B 采用 workflow controller 单写者模型（去锁化边界）

在一次 workflow 执行内，定义明确的写入边界：

- **controller 线程**拥有所有共享可变状态的写权限：
  - `WorkflowCtxStore` 的 publish/resolve（以及 total-bytes 护栏）
  - `WorkflowArtifactsDirectory` 的 publish/get/discard
  - `WorkflowResourceManager` 的 get-or-create / write / commit / discard
  - workflow-level 的事件发射顺序与结果汇总
- **并发线程**只执行纯计算（例如 `run_ir`），并将 `ExecutionResult`（及可选捕获事件）回传给 controller；不得直接写共享状态。
- workflow write nodes（写共享 book 的节点）在 controller 线程按确定性顺序执行，从而不需要 `resources` 内部的 join/lock 复杂度。

该决策的关键点是：**并发保留在计算侧，串行化只发生在共享状态变更侧**。

### Decision 6: v1 不提供版本清理（prune/GC）

v1 版本化输出默认保留所有历史版本：

- 框架 MUST NOT 自动删除 `<root>/versions/<version_id>/...`
- v1 不提供 `scalim-cli outputs prune ...` 等清理命令

如需清理，调用方可通过外部任务按业务策略删除旧版本目录（该操作不需要框架锁）。

## Risks / Trade-offs

- [Breaking DSL] `resources.books.*.path` / `resources.files.*.path` 从“文件路径”升级为“目录 root”，会破坏依赖旧语义的用户配置 → 提供清晰迁移说明（读取 `manifest/latest.json` 获取稳定入口）。
- [Storage growth] 默认保留所有版本，root 目录会增长 → 先保证正确性与可诊断性，后续引入 retention/prune。
- [latest 语义] 并发写同一个 root 时，`latest.json` 会被最后完成的运行覆盖 → 通过“版本目录保留”避免数据丢失；服务端可在业务层按 request-id 固定读取对应版本。
- [FS 原子性] atomic replace 依赖同文件系统 rename 语义；某些网络文件系统的保证较弱 → 先约束为本地/标准 POSIX FS；必要时在实现中加入更保守的 fsync 策略（可选）。

## Migration Plan

1. OpenSpec：补齐 `workflow-versioned-outputs` 新 capability spec，并对 `books/files/sinks/workflow` 的相关 spec 做增量修改（本变更）。
2. DSL：升级 YAML schema + compile/runtime，将 `path` 解释为 output root；移除/废弃 `write_lock` 相关配置面。
3. Runtime：
   - 输出发布改为写入 `<root>/versions/<version_id>/...`，并写 `manifest.json` + 更新 `manifest/latest.json`。
   - workflow 执行改为 controller 单写者；共享状态不再需要 `threading.Lock`（或逐步移除）。
4. 测试与回归：替换所有依赖 `<final>.scalim.lock` 的测试断言；新增并发写同一 root 的回归用例（验证“不同版本并存 + latest 原子更新”）。

## Open Questions

本变更已消除影响可实施性的开放问题；后续新增能力（如 retention/prune、多租户命名空间）将以独立 change 方式推进。
