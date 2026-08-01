---
name: "llman-sdd-apply-cycle"
description: "单个变更的闭环：门禁检查→实施→测试→校验→verify 建议→归档→提交。仅手动触发。Agent MUST NOT 自动调用。"
metadata:
  version: "0.0.66"
  llman_sdd:
    bdd_mode: "off"
    skill_set: "default"
disable-model-invocation: true
---

# LLMAN SDD Apply Cycle

单个变更端到端闭环（手动）。须已 Branch binding 且 `readyToImplement=true`。

**仅手动触发**：`/skill:llman-sdd-apply-cycle <change-id>`

## 工作流

### 0) 门禁 + 状态
```bash
llman sdd show <change-id> --json --type change
llman sdd status <change-id>
```
## 阶段守卫（`stage` / `readyToImplement`）

用权威 JSON 判定（勿凭「完整工件」口头说法）：

```bash
llman sdd show <id> --json --type change
```

解读字段：`stage`、`specsLanded`、`skipSpecsLanding`、`readyToImplement`。

| 条件 | 动作 |
|------|------|
| `stage=draft`（仅 proposal.md） | STOP。长大到 Designed（proposal + tasks；design 按需）→ Branch binding → Specs landing。draft 不能直接 apply/verify。若已有 proposal+design+tasks 仍是 `draft`：未 start/attach —— 在默认分支干净树跑 `change start`，或手动建分支后 `change attach`。**不要**建 `changes/<id>/specs/`，**不要**先在默认分支改 live specs。 |
| `stage=designed` | STOP。先 `change start` / `attach`（Branch binding）。 |
| `stage=full` 且 `readyToImplement=false` | STOP。在**绑定分支**完成 Specs landing（编辑 `llmanspec/specs/**` 并 commit），或设 `skip_specs_landing`。**不要**再跑 `change start`。丢失绑定分支 specs → checkout/重建 + 必要时 `attach --force`。 |
| `readyToImplement=true` | 可通过 apply/verify 前置检查。`changes/<id>/specs/` 预期**不存在**，勿当缺失。 |

- 须在绑定的非默认分支上。
- `readyToImplement` 不为 true → STOP（先 Specs landing 或 `skip_specs_landing`）；**不要**直接 finalize。
- `status` 的 `tasks[]` / `next` 用于进度；实现时仍须阅读 `tasks.md`、proposal/design 与绑定分支上的 live `llmanspec/specs/**`（SSOT）。

### 1) 循环：实施 → 测试
对每个未完成 task：
1. 按 task + live specs 实现（最小改动）
2. 运行 `tasks[].test`（若有）
3. 失败则修复重试（最多 3 次）
4. 勾选 `tasks.md` 为 `[x]`

### 2) 校验
```bash
llman sdd validate <change-id> --strict --no-interactive
```
失败则修复重试（最多 3 次）。

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
- **重试上限**每步 3 次。
- **禁止**写 `changes/<id>/specs/` 或 `change delta`。
- **禁止默认 push/PR**。

## Ethics Governance
- `ethics.risk_level`: medium
- `ethics.prohibited_actions`: 未 `readyToImplement` 就实施/归档、切换其他 change、写 `changes/<id>/specs/`、未校验就提交、默认 push/PR
- `ethics.required_evidence`: `readyToImplement=true`、validate --strict 通过、tasks 全勾、finalize/archive 成功
- `ethics.refusal_contract`: 门禁或校验连续失败 3 次 → 报告 blocker，禁止强行归档
- `ethics.escalation_policy`: 若改动 SDD 工作流 spec/模板，归档前暂停请用户确认
