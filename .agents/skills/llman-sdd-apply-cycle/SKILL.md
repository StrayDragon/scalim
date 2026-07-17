---
name: "llman-sdd-apply-cycle"
description: "单个闭环完成一个变更：实现→测试→校验→归档→提交。仅手动触发。Agent 禁止自动启用。"
metadata:
  version: "0.0.64"
disable-model-invocation: true
---

# LLMAN SDD Apply Cycle

单个闭环完成一个变更的所有步骤：实现未完成任务、跑测试、校验、归档、提交。

**仅手动触发**：`/skill:llman-sdd-apply-cycle <change-id>`

## 工作流

### 0) 读取状态
```bash
llman sdd status <change-id>
```
解析 TOON 输出。`tasks[]` 表列出未完成任务及其测试命令。`next` 字段给出下一步行动。

### 1) 循环：实现 → 测试
对 `tasks[]` 中每个未完成任务（按顺序）：
1. 实现代码变更
2. 运行 `tasks[].test` 字段中的测试命令（如有）
3. 测试失败则修复重试（最多 3 次）
4. 完成后将 `tasks.md` 对应 checkbox 更新为 `[x]`

### 2) 校验
```bash
llman sdd validate <change-id> --strict --no-interactive
```
校验失败则修复重试（最多 3 次）。

### 3) 归档
```bash
llman sdd change archive <change-id>
```

### 4) 提交
```bash
git add -A && git commit -m "<前缀>: <描述>"
```
使用常规提交前缀（feat:/fix:/refactor:）。

## 硬约束
- **不要问**"要不要继续"——直到做完或遇到 blocker。
- **不要切换**到其他变更，直到当前变更归档并提交。
- **重试上限**：每步最多 3 次失败后报告 blocker。
- **SSOT**：以 `llman sdd status` 输出为唯一事实来源。不要直接读 tasks.md/proposal.md/spec 文件。

## Ethics Governance
- `ethics.risk_level`: medium
- `ethics.prohibited_actions`: 在完成前切换到其他变更、直接修改 proposal.md/spec 文件、未经验证就提交
- `ethics.required_evidence`: llman sdd validate --strict 通过、llman sdd change archive 成功、所有 tasks.md 中的 checkbox 已勾选
- `ethics.refusal_contract`: 若校验连续失败 3 次，报告 blocker 而非强制归档
- `ethics.escalation_policy`: 若变更涉及 SDD 工作流规范或模板，在归档前暂停并请用户确认
