---
name: "llman-sdd-onboard"
description: "了解 llman SDD 工作流并完成项目入门。"
---

# LLMAN SDD 入门

使用此 skill 让你快速了解 llman SDD 工作流。

## 步骤
1. 阅读 `llmanspec/config.yaml` 了解项目上下文、约定与规则。
2. 查看当前的变更与 specs。
3. 按照 提案 -> 实施 -> 归档 的流程推进。
4. 使用 `llman sdd graph` 可视化变更依赖关系（depends_on/blocks）。

在执行之前，请先阅读 `llmanspec/config.yaml`，若其中包含 `context` 与 `rules` 请遵循。

常用命令：
- `llman sdd list`（列出变更）
- `llman sdd list --specs`（列出 specs）
- `llman sdd show <id>`（查看 change/spec）
- `llman sdd validate <id>`（校验变更或 spec）
- `llman sdd validate --all`（批量校验）
- `llman sdd migrate`（将旧版 `.md`+fence spec 一次性迁移为独立 `.toon`；幂等）
- `llman sdd archive run <id>`（归档变更）
- `llman sdd archive <id>`（`archive run` 的兼容别名）
- `llman sdd archive freeze [--before YYYY-MM-DD] [--keep-recent N] [--dry-run]`（将已归档目录冻结到单一冷备文件）
- `llman sdd archive thaw [--change <id> ...] [--dest <path>]`（从冷备文件恢复目录）
- `llman sdd graph [CHANGE] [--format mermaid] [--scope active|archived|all] [--depth N]`（生成变更依赖图并输出到标准输出）


## 备注
- `llmanspec/config.yaml` 包含项目上下文、规则、locale 与 skills 路径。
- locale 仅影响模板与 skills，CLI 仍为英文。
- 使用 `llman sdd update-skills` 刷新技能。

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

4) BDD 空 spec 护栏（`BDD is enabled but this spec declares no requirements and no feature_refs`）：
当 `config.yaml` 含 `bdd` 块时，spec 必须要么声明 `requirements`，要么通过 `feature_refs` 指向 `.feature`（point-only 模式）。

备注：
- 每个 spec 是一个独立的 `.toon` 文件；没有 Markdown 外壳，也没有 ```toon fence。
- `null` 表示可选字段缺失。
- 从旧版 `.md`+fence 迁移请使用 `llman sdd migrate`。


## Context
- 执行前先确认当前 change/spec 状态。

## Goal
- 明确本次命令/skill 要达成的可验证结果。

## Constraints
- 变更保持最小化且范围明确。
- 标识符或意图不明确时禁止猜测。

## Workflow
- 以 `llman sdd` 命令结果为事实来源。
- 涉及文件/规范变更时执行校验。

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