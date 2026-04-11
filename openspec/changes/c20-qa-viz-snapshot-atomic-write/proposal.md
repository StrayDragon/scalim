## Meta

- Type: `qa-0`
- Topic: viz snapshot 非原子写入 + run_id 碰撞导致的损坏风险（建议改为 temp+replace）
- Related code:
  - Workflow 完成后重写快照：
    - `src/scalim/workflow/execute.py:1593`~`:1614`（`_report_workflow_viz_finished` 中 `snapshot_path.open("w") + json.dump`）
  - Observer 写快照：
    - `src/scalim/ob/presets/_internal/viz_output.py:147`~`:160`（`_write_snapshot_if_needed`）
  - Run dir 规则（碰撞来源）：
    - `src/scalim/workflow/execute.py:599`（`_bundle_run_dir(..., run_id)`，workflow 固定 `run_id="workflow"`）
    - `src/scalim/ob/presets/_internal/viz_output.py:100`~`:103`（`output_dir/run_id`）

## 背景

viz 产物通常包含：

- `snapshot.json`（图结构/元信息）
- `events.jsonl`（事件流）

这些文件往往会被：

- 前端/可视化工具读取；
- CI/调试时上传作为工件；
- 用户在磁盘上直接查看。

因此 snapshot 的“可读性/完整性”是基本契约：**不能偶发产生半写文件或 JSON 不可解析的文件**。

目前 snapshot 写入采用 `open("w")` + `json.dump` 直接覆盖，缺少原子性与并发冲突保护。

## 现状与风险

### 现状：直接覆盖写

两处代表性实现都类似：

- `with path.open("w") as f: json.dump(snapshot, f, ...)`

### 风险 1：并发写同一路径导致 JSON 截断/交错

当两个进程/线程几乎同时写同一个 snapshot 文件时，常见结果：

- 文件被截断（writer A 打开并 truncate，writer B 也 truncate）；
- 内容交错（A/B 交替写入，生成无效 JSON）；
- 读者读取到“半写入”的文件（尤其是在写入大 snapshot 或磁盘慢时）。

这会直接导致 viz 消费端解析失败。

### 风险 2：run_id 固定导致更容易碰撞

workflow 路径里存在固定 run_id：

- `execute.py` 在 workflow 级 viz 使用 `run_id="workflow"`（见 `replace(bundle_viz_base_config, run_id="workflow")` 与 `_bundle_run_dir(..., "workflow")`）。

如果用户把多个 workflow run 的 viz 输出目录配置为同一个 base_dir，就会出现：

- 多个 workflow 竞争写 `.../workflow/snapshot.json`。

即使最终“最后写入者胜”，也依然有窗口生成损坏文件。

## 例子（可复现思路）

- 在同一输出目录下并发运行两个 workflow（或快速连续触发两次运行），并确保它们的 viz base_dir 相同；
- 两边都在结束时重写 `workflow/snapshot.json`；
- 观察 snapshot 偶发变成：
  - JSON 解析失败；
  - 内容缺失；
  - 结构不完整（节点缺失）。

## 目标

- snapshot 写入具备“读者看到的要么是旧版本，要么是新版本”，不出现半写；
- 允许并发/重入下也不损坏；
- 尽量复用仓库现有的“临时文件 + 原子替换”模式；
- `src/scalim/` 保持 Python 3.6 兼容。

## 方案候选

### 方案 A：snapshot 写入改为 temp+replace（推荐）

做法：

- `tmp = create_temp_path(snapshot_path, ".json.tmp")`
- `json.dump(snapshot, tmp)`（写完 flush；Phase 0 不强制 `fsync`，保持与仓库其它落盘路径一致）
- `Path(tmp).replace(snapshot_path)`

优点：

- 读者永远不会看到半写文件；
- 最小改动，符合仓库现有落盘风格。

缺点：

- 并发写仍然是“最后写入者胜”（但至少不会损坏）。

性价比：

- 极高（小成本消除最痛的损坏风险）。

### 方案 B：在 A 基础上加写锁（对“同一路径多 writer”提供强语义）

做法：

- 对 snapshot_path 引入 `.scalim.lock` 或复用已有写锁机制（见 `workflow/resources_base.py:_acquire_write_lock`）；
- 保证同一时刻只有一个 writer。

优点：

- 除了不损坏，还能避免“两个进程覆盖写”的竞态（至少变成显式失败/等待）。

缺点：

- 需要定义锁冲突策略（fail-fast / wait / stale lock）；
- 实现复杂度略高。

性价比：

- 中到高（取决于是否经常出现并发写同一路径）。

### 方案 C：避免 run_id 固定（降低碰撞概率）

做法：

- 将 workflow 级 run_id 设为 `workflow_exec_id` 或 `workflow_exec_id/workflow` 这样的层级路径；
- 或在 base_dir 下再加一层“本次执行 ID”的目录。

优点：

- 从根源降低碰撞概率；
- 对多次运行的可追溯性更好（每次运行独立目录）。

缺点：

- 改变输出目录结构，可能影响已有工具/脚本的读取路径。

性价比：

- 中（如果当前已经有人依赖固定路径，则迁移成本更高）。

## 推荐方案

Phase 0 推荐落地 **方案 A**（snapshot temp+replace），作为“立即止损”的最小改动。

如果确定存在“同一 base_dir 并发多 workflow”的真实使用场景，再评估叠加：

- 优先考虑 **方案 C（唯一化 run_id）** 做结构级隔离，以尽可能保持无锁设计；
- 仅在确需“同一路径多 writer 的强语义”（等待/失败策略可控）时再引入 **方案 B（写锁）**。

## 验证建议（QA）

- 单测/集成测试：
  - 并发触发 `_write_snapshot_if_needed` 多次，确保最终文件可解析；
  - workflow 结束重写 snapshot 后文件仍可解析且包含必要字段。
- 手工验证：
  - 并发跑两个 workflow 指向同一 viz base_dir，确认 snapshot 不再出现损坏。
