---
name: "llman-sdd-archive"
description: "归档已完成的 llman SDD 变更：合并 delta specs 到主 specs，校验全量，引导 commit。在 verify 报告全绿后运行。支持单个或批量归档。"
metadata:
  version: "0.0.61"
---

# LLMAN SDD 归档

使用此 skill 归档已完成的变更，合并 delta specs 到主 specs，并引导 commit。

## Pipeline 位置

```mermaid
flowchart LR
    verify["llman-sdd-verify<br/>验证"] --> archive
    archive["★ llman-sdd-archive ★<br/>归档（你现在在这里）"]
    archive --> commit["git commit<br/>完成闭环"]

    style archive fill:#fff3cd,stroke:#ffc107,stroke-width:3px
```

> 📍 你现在在归档阶段：pipeline 最后一站。
> 📎 若 specs 逐渐膨胀，可运行 `llman-sdd-specs-compact` 压缩。

## 硬约束

- **必须先通过 verify 阶段全绿**：未通过验证的 change 禁止归档。
- **SSOT 校验**：每个 change 归档前必须通过 `llman sdd validate <id> --strict --no-interactive`。
- **不要问「要不要继续」**：批量归档时间线上一路执行到底，除非遇到无法自动解决的错误。

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
- 可选预览：`llman sdd archive <id> --dry-run`。
- 执行归档：
  - 默认：`llman sdd archive run <id>`
  - 仅工具类变更：`llman sdd archive run <id> --skip-specs`
  - **任一失败立即停止**，报告剩余未处理 ID。
- **BDD-on**：`archive run` 仅将 delta `spec.toon` 合并到主 `spec.toon`。`.feature` 文件由 `llman sdd solidify` 管理——archive 不复制 `.feature` 文件。归档前运行 `solidify <id>`。

### 3) 全量校验
- 全部归档完成后执行：`llman sdd validate --all --strict --no-interactive`。
- 确认归档后的 specs 工件一致。

### 4) Commit 引导
- 输出建议的 commit message（格式：`feat(sdd): archive <id1>, <id2> - <简短总结>`）。
- 提示用户：`git add -A && git commit -m "..."`。
- 若用户要求自动 commit，执行后输出 commit hash。

> 💡 上一阶段 `llman-sdd-verify`（验证通过）→ 本阶段归档后闭环结束。若 specs 逐渐膨胀，可运行 `llman-sdd-specs-compact` 压缩。

## Archive 冷备引导
- 当 archive 目录增长过大时，使用冷备维护：
  - 预览冻结候选：`llman sdd archive freeze --dry-run`
  - 冻结旧归档：`llman sdd archive freeze --before <YYYY-MM-DD> --keep-recent <N>`
  - 需要恢复时：`llman sdd archive thaw --change <YYYY-MM-DD-id>`
- freeze/thaw 仅用于日期归档目录（`YYYY-MM-DD-*`）；建议保留少量最近目录不冻结。


在执行之前，请先阅读 `llmanspec/config.yaml`，若其中包含 `context` 与 `rules` 请遵循。

常用命令：
- `llman sdd context --task "<description>" --paths "<files>"`（获取相关 specs）。使用 pageindex agentic 树检索后端（需配置 `LLMAN_SDD_INDEX_CHAT_MODEL`）。可用 `LLMAN_SDD_INDEX_BACKEND` 预设。
- `llman sdd list`（列出变更）
- `llman sdd list --specs`（列出 specs，含 purpose/scope 元数据）
- `llman sdd show <id>`（查看 change/spec）
- `llman sdd validate <id>`（校验变更或 spec）
- `llman sdd validate --all`（批量校验）
- `llman sdd index rebuild`（重建 pageindex 树索引——无需模型）
- `llman sdd index check`（检查索引新鲜度）
- `llman sdd archive run <id>`（归档变更）
- `llman sdd archive freeze [--before YYYY-MM-DD] [--keep-recent N] [--dry-run]`（冻结归档目录）
- `llman sdd archive thaw [--change <id> ...] [--dest <path>]`（解冻归档）
- `llman sdd graph [CHANGE] [--format mermaid] [--scope active|archived|all] [--depth N]`（生成变更依赖图）


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

2) Change 缺少 delta ops：至少补一个 op + scenario（`llmanspec/changes/<change-id>/specs/<feature-id>/spec.toon`）：
```toon
kind: llman.sdd.delta
ops[1]{op,req_id,title,statement,from,to,name}:
  add_requirement,r1,Title,System MUST do something.,null,null,null
op_scenarios[1]{req_id,id,given,when,then}:
  r1,happy,"",a trigger happens,the outcome is observed
```

3) 表格化行引号错误（"Expected N tabular row values, but got M"）：
值包含**空格**、逗号、冒号或方括号时，必须用双引号包裹。
```toon
# 错误：未加引号的空格值会被拆成多个值
r1,happy,"",a trigger happens,the outcome is observed

# 正确：多词值加引号
r1,happy,"","a trigger happens","the outcome is observed"
```

4) BDD spec 护栏（`BDD is enabled but this spec declares no requirements and has no .feature files`）：
当 `config.yaml` 含 `bdd` 块时，行为规格在 `spec.toon` 的 `scenarios` 中（TOON 是唯一真源）。`.feature` 文件由 `llman sdd solidify` 衍生生成。`requirements` 和 `scenarios` 均为空的 spec 是 ERROR。

备注：
- 每个 spec 是一个独立的 `.toon` 文件；没有 Markdown 外壳，也没有 ```toon fence。
- `null` 表示可选字段缺失。
- 从旧版 `.md`+fence 迁移请使用 `llman sdd migrate`。


## Context
- 执行前先确认当前 change/spec 状态。
- 优先使用 `llman sdd context --task --paths` 获取相关 specs，而非全量读取或猜测。

## Goal
- 明确本次命令/skill 要达成的可验证结果。

## Constraints
- 变更保持最小化且范围明确。
- 标识符或意图不明确时禁止猜测。
- 在读取 spec 全文前，先使用 `llman sdd context --task --paths` 获取相关 specs。
- 判断变更规模后选择路径：行为合约变更走完整 SDD 流程，实现变更走快速路径。

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