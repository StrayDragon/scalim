---
depends_on: []
---

# Proposal: c20-sink-discard-explicit-contract

> **状态**: active（2026-07-18）。  
> **承接**: `tabular-bus-object-sink-accept-precheck` 已把失败清理做成 duck-typed `discard` + `getattr`（MVP）；本变更把该能力提升为 **显式 sink 合约**。

## Why

c15 / 后续 fix 落地后，失败路径语义是：

- 有 `discard` → 调用它（不 promote）
- 没有 → **故意不** `close()`（避免半成品）

这在行为上正确，但合约是隐式的：

1. **类型系统看不见**：wrapper（tee/counting/router）漏转发 `discard` 只能靠 review/Bugbot 发现。
2. **第三方/自定义 sink** 不知道必须实现什么；容易误以为「没 discard 就 close」或「没方法就安全」。
3. **`r922` 只约束「不得 promote」**，没有把 `discard()` 定为 SSOT 清理入口；`close()` 成功提交语义与失败丢弃语义仍易混淆。

产品倾向：每个写出端必须回答两件事——**成功如何 `close`，失败如何 `discard`**。

## What Changes

1. **`ISink`（及行/列子接口）显式声明 `discard()`**：Python ABC `@abstractmethod`（或等价、3.6 兼容的运行时合约）；语义固定为失败路径清理，`MUST NOT` promote 最终文件。
2. **内建 sinks / workbook / 内存捕获 / composition wrappers**：全部实现 `discard()`；无副作用的内存 sink MAY no-op（仍须可调用）；文件类 MUST 关闭句柄/放弃 temp、最终路径不存在。
3. **执行失败路径**：`run_ir` / pipeline / 装配失败 MUST 调用 `discard`（经统一 helper），`MUST NOT` 用 `close()` 代替；成功路径仍仅 `close()`。
4. **收紧 helper**：`discard_sink` / `exit_sink` 以正式方法为准；逐步去掉「探测可选方法」作为主路径（兼容期内 MAY 保留 getattr 兜底，但新代码 MUST 走合约）。
5. **规格**：扩展 `output-sink-contracts`；必要时联动 `execution-structure` / `execution-output-composition` 的失败收尾 MUST。

非目标：

- 改 YAML knobs / 暴露 discard 策略到 DSL。
- 改 `keep_on_failure` staging 默认。
- 自动 coerce 类型、改 accept set / precheck。
- 一次性删除所有 `getattr(discard)`（可分阶段；本 change 以合约 + 内建实现为主）。

## Capabilities

- `output-sink-contracts`（主）：`discard()` 成为 `ISink` 正式方法；与 `r922` 对齐
- `execution-structure`：`run_ir`/engine 失败收尾 MUST discard
- `execution-output-composition`：router/tee/counting 转发 `discard`

## Impact

- **Breaking（有意、窄）**：自定义 `ISink`/`IRowSink`/`IColumnSink` 实现若未提供 `discard`，在 ABC 落地后会在构造/子类检查时失败；须补 no-op 或真实清理。
- **Compat**：内建路径行为应与当前「失败不 promote」一致；成功 `close()` 不变。
- **Perf**：无热路径开销（仅失败/退出）。
- **Ethics**: `risk_level=medium`
  - **prohibited**: 失败路径用 `close()` 伪装成功提交；静默吞掉用户最终半残文件。
  - **required_evidence**: ABC + 内建实现；`run_ir`/ColumnExcel/router 失败无最终文件测试保持绿。
  - **escalation**: 若要对外部已发布自定义 sink 做宽限期/adapter，须人工确认迁移窗口。

## Docs / SSOT

- SSOT：`llmanspec/specs/output-sink-contracts/`（及本 change delta）、`src/scalim/sinks/_internal/base.py` 接口
- 生成物：若触及 agent upgrade 列表，SSOT 为 `agentdev/skills/.../upgrades/*.md`，入口 `just gen-docs` / `just gen-agent-skill`
