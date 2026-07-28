---
name: "llman-sdd-apply-cycle"
description: "单个变更的闭环：实施→测试→校验→归档→提交。仅手动触发。Agent MUST NOT 自动调用。"
metadata:
  version: "0.0.65"
  llman_sdd:
    bdd_mode: "off"
    skill_set: "default"
disable-model-invocation: true
---

# LLMAN SDD Apply Cycle

单个变更的端到端闭环：实施未完成任务、跑测试、校验、归档并提交。

**仅手动触发**：`/skill:llman-sdd-apply-cycle <change-id>`

## 工作流

### 0) 读取状态
```bash
llman sdd status <change-id>
```
解析 TOON 输出。`tasks[]` 表列出未完成任务及测试命令。`next` 字段给出下一步动作。

### 1) 循环：实施 → 测试
按顺序处理 `tasks[]` 中每个未完成任务：
1. 实现代码改动
2. 运行 `tasks[].test` 字段中的测试命令（若有）
3. 测试失败则修复并重试（最多 3 次）
4. 完成后将 `tasks.md` 勾选为 `[x]`

### 2) 校验
```bash
llman sdd validate <change-id> --strict --no-interactive
```
校验失败则修复并重试（最多 3 次）。

### 3) 归档
优先：
```bash
llman sdd change finalize <change-id>
```
（工作区可脏；自动 ff-merge + 文档改名；然后一次 `git commit`。）

Fallback：
```bash
llman sdd change checkpoint <change-id>
llman sdd change archive <change-id>
```

### 4) 提交
```bash
git add -A && git commit -m "<prefix>: <description>"
```
使用约定式 commit 前缀（feat:/fix:/refactor:）。

### 5) 可选清理
```bash
git branch -d <feature-branch>
```
archive/finalize 已将 feature 分支 ff-merge 到默认分支。`git push` / Hosting PR（`gh pr create`/`gh pr merge`）仅为可选——仅当用户或项目明确要求远程审查时才做。

## 硬约束
- **禁止询问**「要不要继续」——除非遇到 blocker，否则一路执行到底。
- **禁止切换**到其他 change，直到当前 change 已归档并提交。
- **重试上限**：每步失败最多重试 3 次，然后报告 blocker。
- **SSOT**：以 `llman sdd status` 输出为唯一事实来源。不要直接读取 tasks.md/proposal.md/spec 文件。
- **禁止默认 push/PR**：未经用户明确要求，**不要**运行 `git push` 或 `gh pr create|merge`。

## Ethics Governance
- `ethics.risk_level`: medium
- `ethics.prohibited_actions`: 当前 change 未完成前切换到其他 change、直接修改 proposal.md/spec 文件、未校验就提交
- `ethics.required_evidence`: llman sdd validate --strict 通过、llman sdd change archive 成功、tasks.md 全部勾选完成
- `ethics.refusal_contract`: 校验失败 3 次后报告 blocker，禁止强行归档
- `ethics.escalation_policy`: 若变更涉及 SDD 工作流 spec 或模板，归档前暂停并请用户确认
