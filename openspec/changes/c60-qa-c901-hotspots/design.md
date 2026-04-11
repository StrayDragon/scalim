## Context

仓库核心链路（workflow 执行、资源写入、可观测性回放）中存在多处以 `# noqa: C901` 放行的复杂度热点。短期放行可接受，但长期会形成稳定的回归风险放大器：

- review 很难覆盖所有分支路径；
- 变更一个分支可能影响多个看似无关的 side effects；
- 单测很难做“规则级覆盖”，往往只能依赖大集成；
- 新贡献者难以理解控制流与契约边界。

本变更定位为 qa-0：不追求“为了过 lint 而机械拆分”，而是把复杂度拆到可命名、可测试、可回滚的边界，并给出可落地的最小切片，为后续 refactor-0（例如 c90 的 execute controller）铺路。

热点代表性点位（以提案列举为基准）：

- `resources_workbook._commit_workbook`：写入规则 + IO/落盘/异常处理 + staged 注册混在一起
- `resources_sheetbook._sheetbook_append_prepare` / `iter_sheetbook_sheet_rows`：大量分支 = 独立业务规则
- `workflow/execute.py` 的 future 完成处理、主调度与 observability capture/replay：本质状态机但以长函数 + 多 dict 状态承载

## Goals / Non-Goals

**Goals:**

- 给每个 C901 热点定义“最小可落地切片”：纯函数提取优先，不改变主控制流
- 每个切片具备明确输入/输出与可单测边界（覆盖规则分支而不是全链路大集成）
- 降低未来在这些热点上改动的回归风险，并为后续更深层的 state/controller 重构提供可验证的分层

**Non-Goals:**

- 不在 qa-0 阶段一次性引入完整 state machine/controller（该工作由 c90 等 refactor-0 承接）
- 不承诺在一个 PR 内消灭所有 `# noqa: C901`（目标是建立拆分路径与护栏，逐步治理）

## Decisions

### 1) 采用“纯函数提取优先”的拆分策略（策略 1）

对每个热点优先提取 2~5 个可单测的纯函数/近似纯函数，保持原函数的控制流结构与调用顺序基本不变：

- `resources_workbook._commit_workbook`
  - 提取 “plan → openpyxl workbook” 构建逻辑（无 IO）
  - 提取 “sheet segments 追加/对齐/公式转义” 规则逻辑（无 IO）
  - 提取 “atomic save” 逻辑（单点处理 `create_temp_path`/`wb.save`/`replace`/异常清理）
- `resources_sheetbook` 的 append/iter 规则
  - 将 `align_by`、`on_mismatch=error|warn|skip`、budget/顺序校验、visible/cutoff 过滤等拆为规则函数
  - 使每个分支对应一个独立可测试的函数返回值（例如 action=error/warn/skip）
- `workflow/execute.py`
  - 对 capture/replay 的“事件分类/整形”提取纯数据函数（分类 + grouping），避免在长函数内交织 side effects
  - 对 outcome 构造、异常分类、policy 决策提取为可测试函数

该策略的核心原则：

- “规则逻辑”与“IO/副作用”拆开：规则函数尽量纯；副作用集中在少数薄层
- 先可测试再抽象：每提取一个函数就补一个小单测覆盖其分支矩阵

### 2) 将更大规模的状态机重构留给后续 refactor-0

对 `execute.py` 的调度/终止条件/释放逻辑，最终形态更像 controller/state（见 c90）。本变更只做：

- 为 controller 化预留边界（纯函数/小对象），降低后续重构成本
- 不在本 qa-0 中改变调度模型与 failure_policy 语义

### 3) 建立轻量治理门禁：新增 C901 必须伴随拆分计划（策略 3）

为避免未来“无意识新增/扩散 `# noqa: C901` 放行点”，建立轻量门禁：

- 任一 `# noqa: C901` MUST 同时带一个治理标记，指向拆分计划（例如引用对应的 OpenSpec change / issue）
- 推荐复用仓库既有的 `pragma: allow-*` 风格（便于脚本扫描与审阅）：
  - 行级：`# noqa: C901  # pragma: allow-c901 plan: <ref>`
  - 文件级：在文件头注释区增加 `# pragma: allow-c901-file plan: <ref>`
- CI/QA 通过简单扫描脚本强制执行该约定；缺少 plan 的 C901 放行点直接 fail-fast

## Risks / Trade-offs

- **漏传参数/状态更新回归**：拆分过程中最常见风险。缓解：先提取纯函数（输入输出显式），并用单测覆盖；主函数保持原调用顺序。
- **机械拆分导致复杂度扩散**：避免“拆完仍共享大量隐式状态”的做法；每个提取函数必须有清晰职责与可测试契约。

## Migration Plan

- Phase 0：先从 `resources_workbook` / `resources_sheetbook` 选择 1~2 个最独立的纯函数切片落地（规则逻辑最清晰）
- Phase 1：对 `execute.py` 的事件分类/整形与 outcome 构造落地纯函数切片
- Phase 2：合并进入 c90 的 controller/state 重构（需要更完整的回归口径）

## Open Questions

- 无。
