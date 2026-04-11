## Context

Scalim 的 viz 产物通常包含：

- `viz_snapshot.json`：依赖图快照/元信息
- `viz_events.jsonl`：事件流（JSONL）

这些文件会被前端/可视化工具读取，也常作为 CI/调试工件上传或被用户直接查看。因此 snapshot 的“可解析/完整”是基本契约：不能偶发产生半写文件或不可解析的 JSON。

当前实现中，snapshot 写入存在两个典型路径：

- workflow 完成后重写 snapshot（`src/scalim/workflow/execute.py:_report_workflow_viz_finished`）
- observer 写 snapshot（`src/scalim/ob/presets/_internal/viz_output.py:_write_snapshot_if_needed`）

两者都使用 `open("w") + json.dump(...)` 直接覆盖文件。这类写法在并发写同一路径、或写入期间被读取时，会出现：

- truncate/交错写入导致 JSON 截断或损坏；
- 读者读到“半写入”的文件。

此外 workflow 级 viz 的 `run_id` 固定为 `"workflow"`，当用户将多个 workflow 的 viz base_dir 指向同一目录时，碰撞概率更高；即使“最后写入者胜”，也仍有窗口产生损坏文件。

约束：

- 运行时保持 Python 3.6 兼容；
- 尽量复用仓库已有的“临时文件 + 原子替换”落盘模式；
- Phase 0 以 qa-0“立即止损”为目标，不引入目录结构迁移或更强一致性语义。

## Goals / Non-Goals

**Goals:**

- `viz_snapshot.json` 写入具备原子性：读者看到的要么是旧版本，要么是新版本，不出现半写/不可解析 JSON
- 覆盖两处 snapshot 写入点（workflow 结束重写 + observer 写入）
- 最小改动落地（qa-0），不引入新配置或迁移成本

**Non-Goals:**

- 不在 Phase 0 改变 viz 输出目录结构或 `run_id` 规则（避免破坏已有读取路径）
- 不在 Phase 0 引入“同一路径多 writer 的强一致性写锁语义”（可作为后续增强）

## Decisions

### 1) Phase 0 采用 temp+replace 的原子写入（方案 A）

对 `viz_snapshot.json` 统一改为：

1. 在同目录创建临时文件（例如通过现有 `create_temp_path(...)` 生成 `*.tmp` 路径）
2. 将 JSON 完整写入临时文件（必要时 flush；Phase 0 不强制 `fsync`，保持与仓库其它落盘路径一致）
3. 使用 `Path.replace(...)` 原子替换到目标路径

这样可保证读者不会看到半写文件；并发写将退化为“最后写入者胜”，但至少文件内容保持可解析。

### 2) 暂不引入写锁；若需降低碰撞优先 run_id 唯一化（方案 C 优先于 B）

Phase 0 只解决“文件损坏/不可解析”的止损问题，不引入写锁：

- **写锁（方案 B）**：需要定义冲突策略（fail-fast / wait / stale lock），并引入跨进程锁治理成本；不是优先路线。
- **唯一化 run_id（方案 C）**：在需要避免“多 workflow 写同一路径”碰撞时，更符合“尽可能无锁”的方向（通过目录隔离降低碰撞概率）。但会改变目录结构与读取路径，需作为单独 phase 评估迁移影响。

## Risks / Trade-offs

- **并发覆盖仍存在**：temp+replace 仅保证文件不损坏，不保证并发多 writer 的最终版本选择（最后写入者胜）。但这符合 Phase 0 的止损定位。
- **平台差异**：`Path.replace` 在主流平台语义接近原子，但仍需通过单测/集成测试覆盖“可解析性”而不是依赖特定文件系统细节。

## Migration Plan

- 无需迁移：输出路径与文件名保持不变，仅增强写入原子性。

## Open Questions

- 无。
