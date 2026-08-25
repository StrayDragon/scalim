---
name: "llman-sdd-archive"
description: "归档已完成的 llman SDD 变更。自动 ff-merge 到默认分支，再将 change 文档改名到 archive/。在 verify 报告全绿后运行。"
metadata:
  version: "0.0.68"
  llman_sdd:
    bdd_mode: "off"
    skill_set: "default"
---

# LLMAN SDD 归档

使用此 skill 归档已完成的变更。前置：verify 全绿，且变更已 Branch binding、Specs landing 完成（或 `skip_specs_landing`；归档时 live specs 已在绑定分支上）。archive/finalize **自动 ff-merge** 到默认分支，**再将** change 文档改名到 `changes/archive/`（脏改名留一次 `git commit`）。`git push` / Hosting PR 仅为可选。

## Pipeline 位置

```mermaid
flowchart LR
    verify["llman-sdd-verify<br/>验证"] --> archive
    archive["★ llman-sdd-archive ★<br/>归档（你现在在这里）"]

    style archive fill:#fff3cd,stroke:#ffc107,stroke-width:3px
```

> 📍 你现在在归档阶段：Git-native 生命周期的最后一站。
> 📎 若 specs 逐渐膨胀，可运行 `llman-sdd-specs-compact` 压缩。

## 硬约束

- **必须先通过 verify 阶段全绿**：未通过验证的 change 禁止归档。
- **须已 Branch binding**：`change start` / `attach` 已完成；无绑定则 STOP。
- **SSOT 校验**：每个 change 归档前必须通过 `llman sdd validate <id> --strict --no-interactive`。
- **不要问「要不要继续」**：批量归档时间线上一路执行到底，除非遇到无法自动解决的错误。
- **收尾不默认导向 PR/push**：archive/finalize 后由 CLI 处理本地 ff-merge，再一次性 `git commit` 提交文档改名。`git push` / Hosting PR 仅为可选——仅当用户或项目明确要求远程审查时才做。**Agent MUST NOT** 因本 skill 默认执行 push 或创建 PR。

## 步骤

### 0) Preflight
- `git status --porcelain`：确认工作区改动属于已完成的 change。
- 若有未预期改动，先处理（stash 或报告）。

### 1) 确认目标变更
- 确定目标 ID：单个或批量（来自用户输入或 `llman sdd list --json`）。
- 始终说明："归档 IDs：<id1>, <id2>, ..."。
- 确认每个 change 都已通过 verify 阶段的全绿验证。

### 2) 逐个归档
- 先逐个校验：`llman sdd validate <id> --strict --no-interactive`。
- 校验失败 → STOP 并报告；不要跳过校验强行归档。
- 可选预览：`llman sdd change archive <id> --dry-run`。
- 执行归档：
  - 默认：`llman sdd change archive <id>`
  - 仅工具类变更：`llman sdd change archive <id> --skip-specs`
  - **任一失败立即停止**，报告剩余未处理 ID。
- **Git-native 收尾**：
  - 前置：已 Branch binding（`change start` / `attach`）；仍在绑定分支上（或 ff-merge 后已在默认分支）。
  - `change archive` / `change finalize` **先自动 ff-merge**（`git merge --ff-only <feature>` 到默认分支），**再**将 change 文档改名到 `changes/archive/`——merge 失败也不会回滚改名。
  - change 下遗留活跃 `*.feature.delta.toon` 是迁移阻断项——归档前须移除/迁移。
  - **推荐：单 commit 收尾（`change finalize`）**——同进程跑门禁 → 自动 ff-merge → 文档改名；结束后工作区脏一次，**一次 `git commit`** 收尾：
    ```text
    1. 实现 live specs + 代码（工作区可保持脏）
    2. llman sdd change finalize <id>   # 门禁 + ff-merge + 文档改名
    3. git commit                       # 一次提交：实现 + frontmatter + archive 改名
    ```
    **`checkpoint_sha` 语义**：finalize 写入的是 attach 时的 `base_sha`，不是实现 commit 的 HEAD（单 commit 模式下实现 commit 尚未发生）。如需精确指向实现 commit，走下方 fallback。
  - **Fallback：多 commit 时序（`checkpoint` + `archive`）**——需要严格 `checkpoint_sha`、或想中途 review 实现快照时使用：
    ```text
    1. git commit   # 提交 live specs + 代码（让工作区干净，checkpoint 才能跑）
    2. llman sdd change checkpoint <id>   # 写入 checkpointed / checkpoint_sha（指向实现 commit HEAD）
    3. git commit   # 提交 proposal.md 的 checkpoint 元数据
    4. llman sdd change archive <id>      # ff-merge + 文档改名
    5. git commit   # 提交 archive 改名
    ```

### 3) 全量校验
- 全部归档完成后执行：`llman sdd validate --all --strict --no-interactive`。
- 确认归档后的 specs 工件一致。

### 4) Commit 引导
- 输出建议 commit message（格式：`feat(sdd): archive <id1>, <id2> - <简短总结>`），若尚未提交则 `git add -A && git commit -m "..."`。
- 可选：ff-merge 后 `git branch -d <feature>`。push / Hosting PR 仅在用户或项目明确要求远程审查时才做。
- 若用户要求自动 commit 归档文档提交，执行后输出 commit hash。
- **archived `depends_on`**：archive 会把 change 目录改名为 `archive/YYYY-MM-DD-<id>`，但 validate 会把指向 archived/frozen id 的 `depends_on` 识别为 INFO（非 ERROR），所以**归档后无需**手动更新其它 change 的 `depends_on` frontmatter。

> 💡 上一阶段 `llman-sdd-verify`（验证通过）→ 本阶段归档后闭环结束。若 specs 逐渐膨胀，可运行 `llman-sdd-specs-compact` 压缩。

## Archive 冷备引导
- 当 archive 目录增长过大时，使用冷备维护：
  - 预览冻结候选：`llman sdd archive freeze --dry-run`
  - 冻结旧归档：`llman sdd archive freeze --before <YYYY-MM-DD> --keep-recent <N>`
  - 需要恢复时：`llman sdd archive thaw --change <YYYY-MM-DD-id>`
- freeze/thaw 仅用于日期归档目录（`YYYY-MM-DD-*`）；建议保留少量最近目录不冻结。

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

校验修复（单轨 feature-as-spec）：

1）缺少头注释（`missing # capability: header comment`）：
每个 `llmanspec/specs/<capability>/<capability>.feature` 必须以以下注释开头：
```
# language: zh-CN
# capability: <capability>
# purpose: 一句话概述
# scope: src/
```

2）tag 语法（`@human constraint scenario must carry an @req:<req_id> tag` / `orphan acceptance scenario`）：
- 规则：`@req:<id> @human` —— statement 放场景描述（须含 MUST/SHALL）。
- 验收：`@executable` 且至少一个 `@req:<id>` 挂到规则。
- `@manual` 须与 `@human` 同用；禁止 `@human` 与 `@executable` 同场景。

3）遗留 `spec.toon`（`legacy spec.toon found ... run ... toon2features`）：
运行 `llman sdd project migrate --kind toon2features --yes`，审阅 diff 后提交。

Git-native 护栏：
- **Branch binding** → **Specs landing**：先 `change start` / `attach`，再在绑定的非默认分支编辑 live `.feature` 并 commit。
- 锁定规则：修改/删除既有 `@human` 场景会触发门禁，除非 proposal frontmatter 带 `rules_edit_acked: true`。
- apply 前须 `readyToImplement=true`（或 `skip_specs_landing`）。收尾优先 `change finalize`。
- 勿使用 `change delta` / solidify / `*.feature.delta.toon`。

## Context
- 执行前先确认当前 change/spec 状态。
- 优先使用 `llman sdd context --task --paths` 获取相关 specs，而非全量读取或猜测。

## Goal
- 明确本次命令/skill 要达成的可验证结果。

## Constraints
- 变更保持最小化且范围明确。
- 标识符或意图不明确时禁止猜测。
- 在读取 spec 全文前，先使用 `llman sdd context --task --paths` 获取相关 specs。
- 判断变更规模后选择路径：行为合约变更走完整 SDD（Branch binding → Specs landing → `readyToImplement` → apply）；实现变更走快速路径（live specs 仍须绑定分支）。
- 勿混淆 Skill 导航与 Git-native 生命周期；勿在默认分支编辑 live `llmanspec/specs/**`。

## Workflow
- 以 `llman sdd` 命令结果为事实来源。
- 涉及文件/规范变更时执行校验。
- 首选 `llman sdd context` 获取相关 specs，而非全量读取或猜测。
- 当 context 不可用时，按错误提示处理（重建 index 或降级到 `list --specs --json`）。

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
