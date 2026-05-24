---
name: "llman-sdd-apply"
description: "实施一个 llman SDD 变更的 tasks，并同步更新 tasks.md 勾选状态。"
---

# LLMAN SDD Apply

使用此 skill 按顺序完成 `llmanspec/changes/<id>/tasks.md`，直到完成或受阻。

## 步骤
1. 选择变更 id：
   - 若已提供，直接使用。
   - 否则先从上下文推断；若不明确，运行 `llman sdd list --json` 并让用户选择。
   - 始终说明："使用变更：<id>"，并告知如何覆盖。
2. 检查前置条件：
   - 必须存在：`llmanspec/changes/<id>/tasks.md`
   - 若缺失，建议先用 `llman-sdd-continue`（或 `llman-sdd-ff`）补齐规划工件，然后 STOP。
3. 阅读上下文文件（视情况而定）：
   - `llmanspec/changes/<id>/proposal.md`
   - `llmanspec/changes/<id>/design.md`（如存在）
   - `llmanspec/changes/<id>/tasks.md`
   - `llmanspec/changes/<id>/specs/**`
4. 展示状态：
   - 进度："N/M tasks complete"
   - 接下来 1–3 个未完成任务（简短概览）
5. 按顺序实施 tasks：
   - 改动保持最小并严格围绕当前任务
   - 完成一项任务后立刻更新 checkbox（`- [ ]` → `- [x]`）
   - 若任务不明确、遇到阻塞、或发现 specs/design 与现实不一致，必须 STOP 并询问用户下一步。
6. 在完成（或暂停）时运行校验：
   ```bash
   llman sdd validate <id> --strict --no-interactive
   ```
   - 若校验无误，建议运行 `llman-sdd-verify`，然后执行归档：`llman sdd archive run <id>`。

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