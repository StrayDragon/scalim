---
name: "llman-sdd-graph"
description: "以 mermaid 图可视化 llman SDD 变更间的依赖关系（depends_on/blocks）。辅助工具，任意阶段可用，不属于主实现 pipeline。"
metadata:
  version: "0.0.66"
  llman_sdd:
    bdd_mode: "off"
    skill_set: "default"
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

行动前先阅读 `llmanspec/config.yaml`，并遵循其中的 `context` 与 `rules`（若有）。

常用命令：
- `llman sdd context --task "<描述>" --paths "<文件>"`（找相关 specs）。使用 pageindex agentic tree 后端（需 `LLMAN_SDD_INDEX_CHAT_MODEL`）。可用 `LLMAN_SDD_INDEX_BACKEND` 预设。
- `llman sdd list`（列出变更）
- `llman sdd list --specs`（列出 specs 及 purpose/scope 元数据）
- `llman sdd show <id>`（展示 change/spec；`--type change --output json` 含 `stage` / `specsLanded` / `skipSpecsLanding` / `readyToImplement`——apply 门禁看 `readyToImplement`，勿凭「完整工件」）
- `llman sdd validate <id>`（校验 change 或 spec）
- `llman sdd validate --all`（批量校验）
- `llman sdd index rebuild`（重建 pageindex 树索引——不需要模型）
- `llman sdd index check`（检查索引新鲜度）
- `llman sdd change new <id>`（仅创建规划壳草稿 `changes/<id>/proposal.md`；不写 live specs）
- `llman sdd change start <id> [--worktree]`（Designed→Full：干净树且在默认分支 → 创建 `sdd/<id>` 分支 + attach；仅 Branch binding，不等于 Specs landing，不等于可 apply）
- `llman sdd change attach <id> [--force]`（绑定已有非默认 feature 分支 + base SHA；拒绝绑到默认分支）
- `llman sdd change finalize <id> [--no-check]`（**推荐单 commit 收尾**——verify 之后；不要求干净树；门禁 + 自动 ff-merge + 文档改名）
- `llman sdd change checkpoint <id> [--no-check]`（干净工作区 + 归档前门禁；严格 sha = HEAD；finalize 的 fallback）
- `llman sdd change diff <id> [--export-patch <path>]`（只读 `base...HEAD` 审查/导出）
- `llman sdd change archive <id>`（封存：自动 ff-merge 到默认分支，再改名到 `changes/archive/`；单 commit 收尾优先 `finalize`）
- `llman sdd archive freeze [--before YYYY-MM-DD] [--keep-recent N] [--dry-run]`（冻结已归档目录）
- `llman sdd archive thaw [--change <id> ...] [--dest <path>]`（从冷备份恢复）
- `llman sdd graph [CHANGE] [--format mermaid] [--scope active|archived|all] [--depth N]`（生成变更依赖图）
- `llman sdd project migrate --kind spec-md2toon`（`.md`+fence → 独立 `.toon`；`partitioned` 已移除）

常见校验修复（TOON 独立文件 spec）：

1) 缺少校验作用域（`Spec valid_scope must not be empty`）：
Main spec 必须在 `.toon` 文档内携带非空的 `valid_scope`。
`llmanspec/specs/<feature-id>/spec.toon`：
```toon
kind: llman.sdd.spec
name: sample
purpose: "One-line overview."
valid_scope[1]: src
requirements[1]{req_id,title,statement}:
  r1,Title,System MUST do something.
scenarios[1]{req_id,id,given,when,then}:
  r1,happy,"",a trigger happens,the outcome is observed
```

2) 表格化行引号错误（"Expected N tabular row values, but got M"）：
值包含**空格**、逗号、冒号或方括号时，必须用双引号包裹。
```toon
# 错误：未加引号的空格值会被拆成多个值
r1,happy,"",a trigger happens,the outcome is observed

# 正确：多词值加引号
r1,happy,"","a trigger happens","the outcome is observed"
```

3) Git-native 护栏（配置了 `bdd:` 时采用 Partitioned SSOT）：
`spec.toon`=约束/不可执行场景；`*.feature`=可执行 GWT（`@req`）。
- **Branch binding** → **Specs landing**：先 `change start` / `attach`，再在绑定的非默认分支编辑 live 文件并 commit。规划壳可短暂在默认分支；**禁止**在默认分支改 live specs；**禁止**写 `changes/<id>/specs/`。
- apply 前须 `readyToImplement=true`（或 `skip_specs_landing`）。收尾（verify 后）优先 `change finalize`，勿在 propose/apply 中途 finalize。
- 勿使用 `change delta` / solidify / `*.feature.delta.toon`。配置了 `bdd:` 且空 requirements 又无 `.feature` = ERROR。

备注：
- 每个 spec 是一个独立的 `.toon` 文件；没有 Markdown 外壳，也没有 ```toon fence。
- `null` 表示可选字段缺失。
- 从旧版 `.md`+fence 迁移请使用 `llman sdd migrate`。

## Ethics Governance
- `ethics.risk_level`：按 `low|medium|high|critical` 标注风险等级。
- `ethics.prohibited_actions`：列出绝对禁止执行的动作。
- `ethics.required_evidence`：列出高影响输出前必须具备的证据。
- `ethics.refusal_contract`：定义何时拒答以及安全替代响应方式。
- `ethics.escalation_policy`：定义何时必须升级为用户确认/人工复核。
