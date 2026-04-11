## Meta

- Type: `qa-0`
- Topic: `# noqa: C901` 热点梳理与“低风险降复杂度”改造建议
- Why now: C901 压制点集中在工作流执行/资源写入/可观测性回放等核心链路，属于回归风险放大器
- Related code (当前热点，行号以仓库最新为准):
  - `src/scalim/workflow/resources_workbook.py:296` (`_commit_workbook`)
  - `src/scalim/workflow/resources_sheetbook.py:249` (`_sheetbook_append_prepare`)
  - `src/scalim/workflow/resources_sheetbook.py:589` (`iter_sheetbook_sheet_rows`)
  - `src/scalim/workflow/execute.py:1107` (`_workflow_process_completed_future`)
  - `src/scalim/workflow/execute.py:1210` (`_execute_workflow_run`)
  - `src/scalim/workflow/execute.py:1617` (`_build_demand_replay_instrumentation`)
  - `src/scalim/workflow/execute.py:1658` (`_replay_captured_workflow_observability`)
  - 另：CLI 也有 C901（见 refactor-0 提案单列处理）：`src/scalim/cli/yaml_dsl.py:909` (`_run_validate`)

## 背景

`C901` 是复杂度门禁（通常代表分支/嵌套/路径过多），在核心模块里用 `# noqa: C901` 放行是可理解的权衡（功能先行、避免阻塞迭代），但长期会带来一组稳定的工程问题：

- 代码评审成本高：很难在一次 review 中覆盖所有路径。
- 回归风险高：改动一个分支，可能影响多个看似无关的行为。
- 单元测试难：函数内部职责耦合，导致测试只能“全链路大集成”，定位回归困难。
- 贡献门槛高：新同学难以快速理解控制流与契约边界。

该提案的目标不是“为了过 lint 拆函数”，而是 **把复杂度拆到可命名、可测试、可回滚的边界**，并形成“下一步 refactor-0 的改造入口”。

## 现状（按模块拆解复杂度来源）

### 1) `resources_workbook._commit_workbook`（工作簿 commit）

核心职责混在一个函数里：

- 动态 optional 依赖：`openpyxl` 导入失败转为工作流错误（`ImportError` → `ScalimWorkflowWriteError`）。
- workbook 写入逻辑：sheet 顺序、header 写入策略、CSV 行迭代、字段 mapping、公式转义等。
- 落盘逻辑：临时文件写入 + 原子替换 staging 文件（`create_temp_path` → `wb.save` → `replace`）与异常清理。
- staged output 注册（供 `resource_manager.commit_all()` 发布）。

复杂度的关键点：它把“业务循环（写数据）”与“IO/落盘/异常处理/资源注册”混在一起。

### 2) `resources_sheetbook._sheetbook_append_prepare` / `iter_sheetbook_sheet_rows`

这两个热点的复杂度主要来自：

- budget/decl_order/sheet_order 更新与校验；
- header 对齐（`align_by`）、不匹配策略（`on_mismatch`=error/warn/skip）、重复写入检测；
- ref 可见性截断与 segment 过滤（DAG 可见性 + `ref.node` cutoff）。

复杂度的关键点：控制流分支多，但“每个分支都对应一个独立的业务规则”。这类函数最适合拆成“规则函数”，避免一个巨型 `if/else`。

### 3) `workflow/execute.py`：执行器与回放逻辑热点

热点函数承担了过多职责：

- future 完成处理（成功/失败/取消、失败策略、释放 artifacts、cache pool 生命周期、emit 事件）。
- 工作流主循环调度（ready queue、submitted futures、max_concurrency、failure_policy=all_fail 语义）。
- capture/replay observability（hook events/observer events/viz observer），涉及事件分类、按 node_id 归并、未知事件兜底。

复杂度的关键点：这部分本质上是状态机/调度器，但目前主要以函数+闭包+多处 dict 状态承载。

## 例子（为什么复杂度会导致“隐性 bug”）

以 `_workflow_process_completed_future` 为例，它同时负责：

- 从 `Future` 得到结果并识别 “captured run” 包装；
- 构造 `WorkflowRunOutcome`（含 diff、error type/message）；
- 处理 `failure_policy`、取消未启动节点；
- 更新多个计数器与释放逻辑；
- emit 事件并注册可重放观测数据。

这种“一个入口，N 个 side effects”的结构，最典型的隐性 bug 是：

- 某条异常路径漏做 cleanup（例如 cache_pool.on_workflow_node_done、artifact release），但只有在极端失败组合下出现；
- 某条成功路径没有触发对应观测事件，导致 viz/diagnostics 缺失；
- 对状态 dict 的局部更新顺序错误，导致后续逻辑误判（例如 node_state/outcomes 与 cancel 的一致性）。

## 目标（QA-0）

- 给出热点函数的“职责拆分建议”与可落地的最小切片；
- 每个切片具备：可单测的纯函数边界、明确输入输出、尽量不改变行为；
- 为后续 `fix-0/refactor-0` 提案提供清晰的切入点与验证口径。

## 推荐方案（按性价比排序的拆分策略）

### 策略 1：先做“纯函数提取”，不动主控制流（最高性价比）

对每个 C901 热点，先提取出 2~5 个纯函数（或近似纯函数）：

- `resources_workbook`：
  - `_build_openpyxl_workbook_from_plan(p) -> Workbook`
  - `_append_sheet_segments(ws, sheet_plan, allow_formulas) -> None`
  - `_save_openpyxl_workbook_atomic(wb, staging_path) -> None`（已经在 sheetbook 中存在类似 helper，可复用/统一）
- `resources_sheetbook`：
  - `_prepare_sheet_plan(...) -> (sheet_plan, expected, mapping, pending_warning, pending_skip)`
  - `_validate_alignment_mismatch(...) -> action`（把 error/warn/skip 的 policy 决策变成函数返回值）
  - `_compute_visible_segments(...) -> segments_snapshot`
- `execute.py`：
  - `_classify_workflow_events(events) -> (started, finished, commit_events, by_node_id, unknown)`（纯数据整形）
  - `_build_outcome_from_exception(...) -> WorkflowRunOutcome`

优点：

- 不改变行为的概率最高；
- 单测可以覆盖“规则/分支”，无需跑全链路；
- review 成本显著降低。

缺点：

- 控制流本身仍复杂（但可读性会明显提升）。

### 策略 2：引入显式 state 对象/小型 state machine（中成本，长收益）

对 `execute.py`，将散落的 dict 状态收敛为一个 `WorkflowRunState`/`WorkflowRunController`（见单独的 refactor-0 提案），把“调度/终止条件/释放”变成显式方法。

优点：

- 真正把复杂度从“长函数”转为“可组合对象”；
- 便于后续扩展（例如更复杂 failure_policy、cache_pool 策略）。

缺点：

- 改造面更大，需要更谨慎的回归验证。

## 不推荐方案

- 仅为了降低复杂度阈值而“机械拆函数”，但拆完仍然共享大量隐式状态/side effects（这会让复杂度从一个函数扩散成多个函数，反而更难排查）。

## 治理门禁（新增 C901 必须伴随拆分计划）

为防止未来继续新增 `# noqa: C901` 放行点而没有治理计划，建立一个轻量但强约束的门禁：

- 任一 `# noqa: C901` MUST 在同一行或文件头注释区标注 `# pragma: allow-c901 ...`，并包含可追踪的拆分计划引用（建议 `plan: <openspec-change-id>` 或 issue 链接）
- CI 在 `just qa` 中启用扫描脚本，缺少 plan 的 C901 放行点直接 fail-fast

示例（行级）：

`def _run_validate(...):  # noqa: C901  # pragma: allow-c901 plan: c80`

## 风险与回滚

- 风险：拆分过程中容易引入“漏传参数/漏更新状态”的回归。
- 缓解：
  - 优先拆纯函数（策略 1），并保持原逻辑调用顺序不变；
  - 对提取函数增加单测覆盖；
  - 关键路径保留对拍测试（例如 workflow 执行 outcomes、资源输出、viz snapshot 结构）。
- 回滚：每个提取切片应独立提交，可单独回滚。

## 验证口径（QA）

- 单测：对每个提取函数覆盖分支（尤其是 policy=error/warn/skip、visible/cutoff 过滤）。
- 集成测试：跑 `just quick-qa-only-py`（或更窄的 tests 子集）确保行为未漂移。
- 可观测性对拍（可选）：对 workflow viz snapshot/events 做结构化快照比对（不要求完全一致，但核心字段一致）。
