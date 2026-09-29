---
depends_on: []
---

# 绑定 call_by 记忆化裸规则为可执行场景

## Why

`llman-sdd spec unbound` 报告 `execution-call-by-memoization` 有 2 条裸规则（r33「Opt-in ctx-free call_by memoization」、r277「Field allow/deny filter for memoization」）：只有 `规则:` 描述与决策表，块内无嵌套 `场景:`，因此不参与可执行行为守护；同文件的 r402/r498 已带嵌套场景，风格不一致。

裸规则按治理口径由 `specs-compact` 压降或补场景；这两条规则描述的是可程序判定行为（env 开关解析、allow/deny 过滤），按「可执行场景优先判据」MUST 落成嵌套 `场景:`。本 change 只补场景文本，不改任何行为合约语义。

## What Changes

- 在 `llmanspec/specs/execution-call-by-memoization.feature` 的 r33 块内补 2 个嵌套 `场景:`：「开关未设置或非正整数时整体关闭」（控制器不产生，行为等价于无记忆化）与「正整数 N 仅准入 ctx-free 字段且每字段容量 N」。
- 在 r277 块内补 2 个嵌套 `场景:`：「deny 优先排除」（deny 命中即排除，无论 allow 取值）与「allow 非空时仅匹配 allow pattern 的字段入选」。
- 顺手修复 r277 决策表第三行缺失的表尾 `|`（描述行排版修复，不改语义）。
- 不改 `src/scalim/` 任何代码：所写场景描述的是既有实现（`src/scalim/execution/executor/runtime/_internal/call_by_memoization.py` 的 env 解析与 `CallByMemoizeFieldFilter.allows`）与既有测试（`tests/execution/test_call_by_memoization_*.py`）已覆盖的行为。

## Capabilities / Impact

- capability：`specs/execution-call-by-memoization`（单轨，仅此一个 `.feature`）。
- SSOT 与生成物边界：`.feature` 为手写 SSOT；本 change 不涉及任何 `.gen.` 文件或 AUTOGEN 注入区块（specs 源不进 `just gen-docs` 产物），`llmanspec/sanitize_rules.yaml` 不涉及本文件（无 api_key/token 字面量）。
- 验证口径：`llman-sdd validate <id> --strict`（目标集含 spec，触发 `specs.check_command = just test` 整批一次）+ `just llmanspec-check`；完成后 `spec unbound` 中该 capability 归 0、`llman-sdd review` unbound 信号归 0。
