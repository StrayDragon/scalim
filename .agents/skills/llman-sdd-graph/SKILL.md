---
name: "llman-sdd-graph"
description: "用 mermaid 图可视化 change 依赖（depends_on/blocks）。辅助工具，任意阶段可用。"
metadata:
  version: "0.7.0"
---

# LLMAN SDD 依赖图

可视化 change 之间的依赖关系。辅助工具，不属于主 pipeline（propose → apply → verify → archive），任意阶段可用。

## 用法

**聚焦视图（seed 模式）**——指定 change 及其关系邻域：

```bash
llman-sdd graph <change-id>              # 该 change + 直接关系（depth 1）
llman-sdd graph <change-id> --depth 3    # 递归 3 层
llman-sdd graph <change-id> --depth 0    # 仅自身
```

沿 upstream（depends_on）、downstream（被谁依赖）、blocks 三方向遍历，自动发现活跃与已归档 change。

**全局视图（scope 模式）**——以 scope 内节点为根，沿 `depends_on` 展开一层（depth 1，缺省），避免无限依赖链；`--depth` 同样约束全图模式：

```bash
llman-sdd graph                          # 活跃 change + 直接依赖（depth 1 缺省）
llman-sdd graph --scope archived         # 已归档 + 直接依赖
llman-sdd graph --scope all              # 全部 + 直接依赖
llman-sdd graph --depth 0                # 仅 scope 内节点（不拉依赖 target）
llman-sdd graph --depth 3                # 依赖链递归展开 3 层
```

## 输出

- mermaid flowchart 到 stdout，可管道到文件或渲染器：
  ```
  llman-sdd graph c50 > deps.mmd
  llman-sdd graph c50 --depth 2 | mmdc -i - -o deps.png
  ```
- 已归档 change 以 "✓ done" 后缀和绿色高亮显示；互不相连的分组各渲染为独立 subgraph，标注 "Active" / "Done" / "Mixed"。

## 依赖声明（proposal frontmatter）

```yaml
---
depends_on:
  - other-change-id
blocks:
  - blocked-change-id
---
```

> 命令细节用 `llman-sdd <cmd> --help` 查看；命令参考以 CLI 为准，skill 不内嵌命令表。
> 文中「规约」= 本项目 `llmanspec/specs/` 下的 `.feature` 文件；用 `llman-sdd list --specs` / `llman-sdd show <capability>` 查全文。

## Ethics Governance
- `ethics.risk_level`：low——仅读写本仓库与 `llmanspec/`，无外发动作；正文另有声明时从其声明。
- `ethics.prohibited_actions`：违反正文「硬约束」的动作；未经用户明确要求的 push / PR / 外部上传。
- `ethics.required_evidence`：结论须有命令输出或文件路径佐证；门禁状态以 `llman-sdd validate` 为准。
- `ethics.refusal_contract`：门禁 CRITICAL 未清零 → 拒绝进入下一阶段；自修复达上限 → 报告 blocker。
- `ethics.escalation_policy`：改动 SDD 合约/模板或执行不可逆动作前，暂停并请用户确认。
