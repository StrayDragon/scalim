## Meta

- Type: `fix-0`
- Topic: workflow 资源输出的 `write_lock` 配置未生效（跨进程并发写最终输出路径时“最后写入者胜”）
- Related code:
  - 写锁实现（已存在）：
    - `src/scalim/workflow/resources_base.py:179`（`_acquire_write_lock`）
    - `src/scalim/workflow/resources_base.py:238`（`_release_write_lock`）
  - 配置解析并传入（但未使用）：
    - `src/scalim/workflow/execute.py:724`~`:801`（`workbook_write_lock_by_id` / `export_write_lock`）
    - `src/scalim/workflow/execute.py:894`~`:910`（传入 `WorkflowResourceManager(..., workbook_write_lock=...)`）
  - Resource manager publish：
    - `src/scalim/workflow/resources_base.py:404`~`:431`（`Path(staged_path).replace(final_path)`，无锁）
  - 未使用证据：
    - `_workbook_write_lock` 仅存储未引用：`src/scalim/workflow/resources_base.py:254`、`src/scalim/workflow/resources_base.py:290`
  - 对照：sink 层已使用写锁（参考实现）
    - `src/scalim/sinks/_internal/excel.py:244`~`:270`

## 背景

workflow 的资源写入采用“两阶段”：

1) 每个资源先写入 staging（通常在 workflow 执行目录/临时目录），保证中间产物可控；  
2) workflow 结束时统一 `commit_all()` 发布 staged 输出到最终 `final_path`（原子 replace）。

这个设计对“单进程/单工作流”非常合理。但在以下场景中会出现真实竞态：

- 同一个最终 `final_path` 被多个 workflow 进程同时写入（例如多次调度同一报表输出到固定路径）。

仓库已经有写锁机制 `_acquire_write_lock(output_path + ".scalim.lock")`，并且 workflow DSL/IR 里也支持配置 `write_lock`（至少 book 与 sheetbook export 侧能配置/解析），但目前资源管理器发布阶段未使用该锁，导致该配置实际无效。

这属于“功能承诺与实际行为不一致”的 fix-0 问题。

## 现状与问题

### 现状

- publish 阶段直接 `Path(staged_path).replace(final_path)`（原子，但不互斥）。
- workbook/sheetbook/csv 等资源的 `write_lock` 配置被解析并传入 manager，但 manager 未消费。

### 问题表现

当两个 workflow 并发写同一路径：

- 文件不会半写（replace 原子），但 **最终文件来自最后一个完成发布的 workflow**；
- 对用户而言，表现为“输出偶发被覆盖/不稳定”，且难以追踪；
- 更糟糕的是：用户可能以为打开了 `write_lock` 就会 fail-fast，但实际没有。

## 例子

- workflow A 与 workflow B 都输出 `reports/daily.xlsx`；
- 两者并发运行；
- A 先完成 publish，B 后完成 publish；
- 最终磁盘上只有 B 的版本，A 的输出被覆盖；
- 如果运行时采集 audit/viz，很可能出现“事件显示 A 成功，但最终文件不是 A”。

## 目标

- `write_lock=true` 的资源在 publish 时必须互斥：
  - 要么阻止并发 writer（fail-fast 报错）；
  - 要么串行化 publish（可选策略）。
- 保持 staging + replace 的原子性；
- 尽量把改动限制在 publish 边界（避免扩大到写入/计算阶段）；
- Python 3.6 兼容。

## 推荐修复方案（最小可落地）

### 方案 A：在 `_publish_staged_outputs` 里按 `final_path` 获取写锁（推荐）

做法：

- 在发布每个 staged output 前，根据资源类型/配置判断是否需要写锁：
  - workbook：查 `self._workbook_write_lock[resource_id]`
  - sheetbook export：查 `sheetbook_def.export_write_lock`
  - csv：可选支持（如果 IR/配置已有对应项；否则先不做）
- 如果需要：
  - `lock_path = _acquire_write_lock(final_path, owner={workflow_exec_id, resource_type, resource_id, staged_path})`
  - `Path(staged_path).replace(final_path)`（或 copy-atomic）
  - finally `_release_write_lock(lock_path)`

优点：

- 改动集中在最终 publish 阶段；
- 语义清晰：只有“真正影响最终文件”的那一步需要互斥；
- 即使两个 workflow 都跑完计算，也会在 publish 边界 fail-fast，避免“静默覆盖”。

缺点：

- 可能让冲突从“静默覆盖”变成“发布失败”（这是期望行为，但要在文档/错误消息里说清楚）。

### 方案 B：在资源写入（commit 生成 staged）阶段提前获取锁（不推荐作为首选）

缺点：

- 锁持有时间更长（从计算开始到发布结束），更易导致长时间阻塞；
- 工作流失败/取消时更难保证释放锁。

## 兼容性与行为变化

- 对未启用 `write_lock` 的用户：行为不变（仍可能覆盖，但这是显式选择）。
- 对启用 `write_lock` 的用户：行为从“可能覆盖”变为“冲突时报错”或“串行化发布”（取决于策略），属于修复承诺行为。

## 性价比

- 成本：中（需要把 write_lock 配置从 execute → manager → publish 串起来，补测试）。
- 收益：高（修复并发写导致的非确定性覆盖；让配置真正生效）。

## 验证建议（测试口径）

- 单测（推荐）：
  - 使用临时目录构造两个 manager/两个 workflow_exec_id 并发 publish 同一 final_path：
    - 启用 write_lock：断言其中一个 publish 抛出 `ScalimWorkflowWriteError` 且 diff 包含 lock_path/owner 信息；
    - 禁用 write_lock：断言不会抛错且最终内容来自最后一次 replace（现状行为）。
- 回归：
  - 跑 `tests/workflow/test_workflow_resources_coverage.py`（已有写锁相关用例，可扩展）。

