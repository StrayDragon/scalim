# Design

## 决策与取舍

- **只补嵌套 `场景:`，不新增/不改 `规则:` 条款**：r33/r277 的 MUST 语义保持原样，场景是既有合约的可执行示例化（治理口径：可程序判定行为 MUST 落成嵌套场景，裸规则交 specs-compact 压降——本例选择补场景）。
- **场景措辞对齐既有实现与测试**：
  - r33 场景对应 `build_call_by_memoization_controller()`（`src/scalim/execution/executor/runtime/_internal/call_by_memoization.py`）：`SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES` 未设置/非正整数 → 返回 `None`（控制器不产生）；正整数 `N` → 控制器启用，候选门为 executor 的 `not use_ctx` 判定（仅 ctx-free 字段），每字段 `max_entries=N`。
  - r277 场景对应 `CallByMemoizeFieldFilter.allows`：deny pattern 命中即排除（优先于 allow）；allow 非空时需匹配任一 allow pattern。
- **顺手修 r277 决策表第三行表尾 `|`**：纯描述行排版（Gherkin 描述按行保留），不改条款语义；锁定规则报告制，`change diff` 将按 `@req:r277` 出 WARNING，接受。
- **不改代码、不加测试文件**：场景描述的行为已被 `tests/execution/test_call_by_memoization_executor.py` / `test_call_by_memoization_filter.py` 覆盖；行为守护由既有测试承担，spec 侧以结构 bound（unbound 归 0）为验收。

## 文档/生成物边界

- 本 change 仅手写 `llmanspec/specs/execution-call-by-memoization.feature`（SSOT）；不涉及 `.gen.` 生成物、AUTOGEN 注入区块、docs-site 或 agent skill 生成入口（`just gen-docs` / `just gen-agent-skill` 均不消费 specs 源）。

## 验证口径（drift gate）

- `llman-sdd validate <id> --strict`：结构校验 + 目标集含 spec 时整批执行一次 `specs.check_command = just test`。
- `just llmanspec-check`：sanitize + validate 工件门。
- `llman-sdd spec unbound --limit 0`：`execution-call-by-memoization` 归 0；`llman-sdd review`：criticalCount 0。
