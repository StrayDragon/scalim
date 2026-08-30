---
name: "llman-sdd-apply-cycle"
description: "单个变更的闭环：门禁检查→实施→测试→校验→verify 建议→归档→提交。仅手动触发。Agent MUST NOT 自动调用。"
metadata:
  version: "0.0.72"
disable-model-invocation: true
---

# LLMAN SDD Apply Cycle

单个变更端到端闭环（手动）。须已 Branch binding 且 `readyToImplement=true`。

**仅手动触发**：`/skill:llman-sdd-apply-cycle <change-id>`

## 工作流

### 0) 门禁 + 状态
```bash
llman sdd show <change-id> --json --type change
```
> 阶段判定：用 `llman sdd show <id> --json --type change` 的 `stage` / `readyToImplement` 字段；完整判定表见 llman-sdd-apply。

- 须在绑定的非默认分支上。
- `readyToImplement` 不为 true → STOP（先 Specs landing 或 `skip_specs_landing`）；**不要**直接 finalize。
- 进度以 `tasks.md` checkbox 为准（或 `llman sdd list` 的任务计数）；实现时仍须阅读 `tasks.md`、proposal/design 与绑定分支上的 live `llmanspec/specs/**`（SSOT）。

### 1) 循环：实施 → 测试
对每个未完成 task：
1. 按 task + live specs 实现（最小改动）
2. 运行 `tasks[].test`（若有）
3. 失败则修复重试（自修复预算与 `llman-sdd-apply` 一致：上限 8 轮）
4. 勾选 `tasks.md` 为 `[x]`

### 2) 校验
```bash
llman sdd validate <change-id> --strict --no-interactive
```
失败则修复重试（自修复预算与 `llman-sdd-apply` 一致：上限 8 轮）。

### 3) Verify（推荐）
优先跑 `llman-sdd-verify`（或等效双轴自检）。有 CRITICAL → STOP，勿归档。

### 4) 归档
优先：
```bash
llman sdd change finalize <change-id>
```
（工作区可脏；ff-merge + 文档改名；再一次 `git commit`。）

Fallback：`checkpoint` → `archive`（见 `llman-sdd-archive`）。

### 5) 提交
```bash
git add -A && git commit -m "<prefix>: <description>"
```

### 6) 可选清理
```bash
git branch -d <feature-branch>
```
push / Hosting PR 仅当用户明确要求。

## 硬约束
- **禁止询问**「要不要继续」——除非 blocker，否则一路到底。
- **禁止切换**其他 change，直到本 change 已归档并提交。
- **重试上限**：自修复遵循 `llman-sdd-apply` 的 8 轮预算（含 diagnose 升级路径）。
- **禁止**写 `changes/<id>/specs/` 或 `change delta`。
- **禁止默认 push/PR**。

## Ethics Governance
- `ethics.risk_level`: medium
- `ethics.prohibited_actions`: 未 `readyToImplement` 就实施/归档、切换其他 change、写 `changes/<id>/specs/`、未校验就提交、默认 push/PR
- `ethics.required_evidence`: `readyToImplement=true`、validate --strict 通过、tasks 全勾、finalize/archive 成功
- `ethics.refusal_contract`: 门禁或校验自修复 8 轮仍失败 → 报告 blocker，禁止强行归档
- `ethics.escalation_policy`: 若改动 SDD 工作流 spec/模板，归档前暂停请用户确认
