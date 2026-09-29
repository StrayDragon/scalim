---
name: "llman-sdd-draft"
description: "把 change 想法记成草案（仅 proposal.md，不问 id）。随手记 idea/未来需求；落实时走 propose。"
metadata:
  version: "0.6.0"
---

# LLMAN SDD 草案（Draft）

把 change 想法记成**草案**（仅 `proposal.md` skeleton）——「先记下来」的轻量入口：不判断规模、不写 tasks、不改 specs、不 attach。落实时用 `llman-sdd-propose` 正式化。

## Pipeline 位置

```mermaid
flowchart LR
    draft["★ llman-sdd-draft"] -.->|"正式化"| propose["llman-sdd-propose"]
    propose --> apply["llman-sdd-apply"] --> verify["llman-sdd-verify"] --> archive["llman-sdd-archive"]

    style draft fill:#fff3cd,stroke:#ffc107,stroke-width:3px
```

> 📍 草案阶段 → 下一步：完善 `proposal.md`，然后 `llman-sdd-propose` 正式化。

## 硬约束

- **MUST NOT 询问 change id**：由 `change new --from` 从描述推导并告知用户。
- **MUST NOT 创建 tasks/design/specs/attach**：只建 `proposal.md` 草案；完整规划归 `llman-sdd-propose`。
- **MUST NOT 判断变更规模**：那是 propose 的职责。用户想开始实现 → 建议 `llman-sdd-propose`。
- **适用边界**：描述明显涉及 MUST/SHALL 合约变更或多文件改动时，建议 `llman-sdd-propose`——但仍先建草案以免想法丢失。
- **frontmatter 有固定 schema**：`proposal.md` 只接受 `llmanspec/AGENTS.md`「Change Proposal Frontmatter SSOT」的合法字段（`depends_on`、`blocks`、`branch`、`base_sha`、`needs_specs_change` 等）；`status`/`title`/`priority`/`author` 会被 `llman-sdd validate` 报 ERROR。生命周期阶段是推断量（用 `llman-sdd show`/`list` 查），绝不写进 frontmatter。正文 MUST NOT 复读 frontmatter 字段（不要 `## Status` 段）；H1 用人类可读标题，不复读 change id。

## 步骤

### 0) Preflight
- 读 `llmanspec/config.yaml`；`llmanspec/` 不存在则提示先跑 `llman-sdd init`，然后 STOP。

### 1) 捕获描述
- 直接采用用户描述（如「draft: 加一个导出 json 的命令」「记一下: sdd change 应该支持 worktree」）。**MUST NOT 询问 change id。**

### 2) 创建草案
```bash
llman-sdd change new --from "<用户描述>"
```
- CLI 生成合法 kebab-case id，在 `llmanspec/changes/<id>/` 建 `proposal.md`（含 `## Why` / `## What Changes` TODO 段），并打印 id 与路径。
- id 冲突时 CLI 非零退出；建议改写描述或 `--force` 覆盖（草案罕见）。

### 3) 告知并交接
- **MUST 告知生成的 id**（「已创建草案 change `<id>`，路径 `llmanspec/changes/<id>/proposal.md`」）。
- 建议下一步：完善 `proposal.md`（Why / What Changes / Capabilities / Impact）；落实时跑 `llman-sdd-propose`。

> 命令细节用 `llman-sdd <cmd> --help` 查看；命令参考以 CLI 为准，skill 不内嵌命令表。
> 文中「规约」= 本项目 `llmanspec/specs/` 下的 `.feature` 文件；用 `llman-sdd list --specs` / `llman-sdd show <capability>` 查全文。

## Ethics Governance
- `ethics.risk_level`：low——仅读写本仓库与 `llmanspec/`，无外发动作；正文另有声明时从其声明。
- `ethics.prohibited_actions`：违反正文「硬约束」的动作；未经用户明确要求的 push / PR / 外部上传。
- `ethics.required_evidence`：结论须有命令输出或文件路径佐证；门禁状态以 `llman-sdd validate` 为准。
- `ethics.refusal_contract`：门禁 CRITICAL 未清零 → 拒绝进入下一阶段；自修复达上限 → 报告 blocker。
- `ethics.escalation_policy`：改动 SDD 合约/模板或执行不可逆动作前，暂停并请用户确认。
