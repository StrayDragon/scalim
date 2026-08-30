---
name: "llman-sdd-graph"
description: "以 mermaid 图可视化 llman SDD 变更间的依赖关系（depends_on/blocks）。辅助工具，任意阶段可用，不属于主实现 pipeline。"
metadata:
  version: "0.0.72"
---

# LLMAN SDD 依赖图

使用此 skill 可视化变更之间的依赖关系。

## Pipeline 位置

```mermaid
flowchart LR
    pipeline["主 pipeline:<br/>propose → apply → verify → archive"]
    graph["📎 llman-sdd-graph<br/>依赖可视化（辅助工具）"]
    graph -.->|任意阶段可用| pipeline

    style graph fill:#e8f4e8,stroke:#28a745,stroke-width:2px
```

> 📎 辅助工具，可在 pipeline 任意阶段使用。需要提案 → `llman-sdd-propose`；需要实施 → 仅当 `readyToImplement=true` 时用 `llman-sdd-apply`。

## 用法

**聚焦视图（seed 模式）：** 展示指定变更及其关系邻域。

```bash
llman sdd graph <change-id>              # 该变更 + 直接关系（depth 1）
llman sdd graph <change-id> --depth 3    # 递归 3 层
llman sdd graph <change-id> --depth 0    # 仅该变更自身
```

seed 模式沿 upstream（depends_on）、downstream（被谁依赖）、blocks 三个方向遍历，自动发现活跃和已归档变更。

**全局视图（scope 模式）：** 按范围展示所有变更。

```bash
llman sdd graph                          # 所有活跃变更（默认）
llman sdd graph --scope archived         # 所有已归档（已完成）变更
llman sdd graph --scope all              # 全部
```

## 输出

- 输出为 mermaid flowchart 到标准输出，可管道到文件或渲染器：
  ```
  llman sdd graph c50 > deps.mmd
  llman sdd graph c50 --depth 2 | mmdc -i - -o deps.png
  ```
- 已归档（已完成）变更以 "✓ done" 后缀和绿色高亮显示。
- 当图中存在互不相连的分组时，每组渲染为独立的 subgraph，标注 "Active"、"Done" 或 "Mixed"。

## 提案 frontmatter 格式

```yaml
---
depends_on:
  - other-change-id
blocks:
  - blocked-change-id
---

## Why
...
```

> 💡 这只是辅助工具 — 主流程：`llman-sdd-propose`（含 Branch binding + Specs landing）→ `llman-sdd-apply`（须 `readyToImplement`）→ `llman-sdd-verify` → `llman-sdd-archive`。

> 命令细节用 `llman sdd <cmd> --help` 查看；命令参考以 CLI 为准，skill 不内嵌命令表（r139）。

## Ethics Governance
- `ethics.risk_level`：low——仅读写本仓库与 `llmanspec/`，无外发动作；正文另有声明时从其声明。
- `ethics.prohibited_actions`：违反正文「硬约束」的动作；未经用户明确要求的 push / PR / 外部上传。
- `ethics.required_evidence`：结论须有命令输出或文件路径佐证；门禁状态以 `llman sdd validate` 为准。
- `ethics.refusal_contract`：门禁 CRITICAL 未清零 → 拒绝进入下一阶段；自修复达上限 → 报告 blocker。
- `ethics.escalation_policy`：改动 SDD 合约/模板或执行不可逆动作前，暂停并请用户确认。
