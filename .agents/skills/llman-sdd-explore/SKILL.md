---
name: "llman-sdd-explore"
description: "进入 llman SDD 探索模式（仅思考；不做实现）。"
---

# LLMAN SDD Explore

当用户希望在开始实现之前先理清思路、调查问题或澄清需求时，使用此 skill。

**重要：探索模式只用于思考，不用于实现。**
- 你可以阅读文件、搜索代码、调查代码库。
- 如果用户需要，你可以创建/更新 llman SDD artifacts（proposal/specs/design/tasks）。
- 你绝对不能在探索模式下写应用代码或实现功能。

## 探索姿态（Stance）
- 好奇而不教条
- 以真实代码为依据
- 需要时用 ASCII 图可视化
- 同时保留多个选项与权衡

## 建议动作
1. 澄清目标与约束（问 1–3 个问题）。
2. 先看上下文：`llman sdd list --json`
3. 如果某个 change id 相关，阅读 `llmanspec/changes/<id>/` 下的 artifacts。
4. 探索 2–3 个选项与权衡。
5. 当结论逐渐清晰时，建议用户把它记录下来（不要自动写入）：
   - 范围变化 → `proposal.md`
   - 需求变化 → `llmanspec/changes/<id>/specs/<capability>/spec.md`
   - 设计决策 → `design.md`
   - 新工作项 → `tasks.md`

## 退出探索模式
当用户准备开始实现时，建议：
- `llman-sdd-propose`（提出提案并生成工件）
- `llman-sdd-new-change`（创建 change）
- `llman-sdd-ff`（一次性创建所有 artifacts）
- `llman-sdd-apply`（按 tasks 实施）
若用户在探索模式中要求你开始实现，STOP 并提醒其先退出探索模式。

在执行之前，请先阅读 `llmanspec/config.yaml`，若其中包含 `context` 与 `rules` 请遵循。

常用命令：
- `llman sdd list`（列出变更）
- `llman sdd list --specs`（列出 specs）
- `llman sdd show <id>`（查看 change/spec）
- `llman sdd validate <id>`（校验变更或 spec）
- `llman sdd validate --all`（批量校验）
- `llman sdd convert --to <style> --project`（显式风格迁移；toon/yaml 为 experimental）
- `llman sdd archive run <id>`（归档变更）
- `llman sdd archive <id>`（`archive run` 的兼容别名）
- `llman sdd archive freeze [--before YYYY-MM-DD] [--keep-recent N] [--dry-run]`（将已归档目录冻结到单一冷备文件）
- `llman sdd archive thaw [--change <id> ...] [--dest <path>]`（从冷备文件恢复目录）
- `llman sdd graph [CHANGE] [--format mermaid] [--scope active|archived|all] [--depth N]`（生成变更依赖图并输出到标准输出）


## Context
- 执行前先确认当前 change/spec 状态。

## Goal
- 明确本次命令/skill 要达成的可验证结果。

## Constraints
- 变更保持最小化且范围明确。
- 标识符或意图不明确时禁止猜测。

## Workflow
- 以 `llman sdd` 命令结果为事实来源。
- 涉及文件/规范变更时执行校验。

## Decision Policy
- 高影响歧义必须先澄清。
- 已知校验错误下禁止强行继续。

## Output Contract
- 汇总已执行动作。
- 给出结果路径与校验状态。

## Ethics Governance
- `ethics.risk_level`：按 `low|medium|high|critical` 标注风险等级。
- `ethics.prohibited_actions`：列出绝对禁止执行的动作。
- `ethics.required_evidence`：列出高影响输出前必须具备的证据。
- `ethics.refusal_contract`：定义何时拒答以及安全替代响应方式。
- `ethics.escalation_policy`：定义何时必须升级为用户确认/人工复核。

## Future 到执行的规划
- 将 `llmanspec/changes/<id>/future.md` 视为候选待办池，而不是静态备注。
- 审查 `Deferred Items`、`Branch Options`、`Triggers to Reopen`，并把每项归类为：
  - `now`（需要立即转化为可执行工作）
  - `later`（保留在 future.md，补充明确触发信号）
  - `drop`（移除或标记拒绝并说明原因）
- 对每个 `now` 项，产出明确落地路径：
  - 后续 change id（`add-...`、`update-...`、`refactor-...`）
  - 受影响 capability/spec 路径
  - 第一条可执行动作（`llman-sdd-propose`、`llman-sdd-new-change`、`llman-sdd-continue`、`llman-sdd-ff` 或 `llman-sdd-apply`）
- 保持可追溯性：在新 proposal/design/tasks 中引用来源 future 条目。
- 若存在高不确定性，先暂停并提问，再创建新变更工件。