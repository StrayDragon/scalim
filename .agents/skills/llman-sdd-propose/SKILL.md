---
name: "llman-sdd-propose"
description: "提出一个新变更并一次性生成规划工件。"
---

# LLMAN SDD 提案（Propose）

创建一个新变更，并一次性生成所有规划工件（proposal + delta specs + tasks；design 可选），然后执行校验并建议下一步动作。

## 步骤
1. 收集输入：
   - 变更的简要描述
   - change id（若未给出则推导；kebab-case，动词前缀：`add-`、`update-`、`remove-`、`refactor-`）
   - 受影响的 capability/capabilities（用于命名 `specs/<capability>/`）
   - 在写入任何文件前确认最终 id
2. 确保项目已初始化：
   - 必须存在 `llmanspec/`；若不存在，提示先运行 `llman sdd init`，然后 STOP。
3. 创建 `llmanspec/changes/<change-id>/` 与 `llmanspec/changes/<change-id>/specs/`。
   - 若变更已存在，STOP 并建议使用 `llman-sdd-continue`。
4. 在 `llmanspec/changes/<change-id>/` 下创建工件：
   - `proposal.md`（Why / What Changes / Capabilities / Impact）
   - 为每个 capability 创建 `specs/<capability>/spec.md`，并匹配项目配置的 `spec_style`（`toon`）：
     - 建议优先通过 authoring helpers 生成，确保 fenced payload 与 `spec_style` 一致：
       - `llman sdd delta skeleton <change-id> <capability>`
       - `llman sdd delta add-op ...`
       - `llman sdd delta add-scenario ...`
     - 至少包含一个 `add_requirement`/`modify_requirement` op（statement 必须含 MUST/SHALL），并且至少包含一行匹配的 op scenario
   - 仅在涉及权衡/迁移时创建 `design.md`
   - `tasks.md`：按顺序拆分为可勾选清单（包含校验命令）
5. 校验：
   ```bash
   llman sdd validate <change-id> --strict --no-interactive
   ```
   此步骤必须通过后才能继续。若出现 TOON 解析错误，需修复引号：表格化行中包含逗号/冒号/方括号的值必须用双引号包裹。
6. 总结已创建内容，并建议使用 `llman-sdd-apply` 进入实现阶段。

在执行之前，请先阅读 `llmanspec/config.yaml`，若其中包含 `context` 与 `rules` 请遵循。

常用命令：
- `llman sdd list`（列出变更）
- `llman sdd list --specs`（列出 specs）
- `llman sdd show <id>`（查看 change/spec）
- `llman sdd validate <id>`（校验变更或 spec）
- `llman sdd validate --all`（批量校验）
- `llman sdd convert --to <style> --project`（显式风格迁移；toon/yaml 为 experimental）
- `llman sdd archive run <id>`（归档变更）
- `llman sdd archive <id>`（`archive run` 的兼容别名）
- `llman sdd archive freeze [--before YYYY-MM-DD] [--keep-recent N] [--dry-run]`（将已归档目录冻结到单一冷备文件）
- `llman sdd archive thaw [--change <id> ...] [--dest <path>]`（从冷备文件恢复目录）
- `llman sdd graph [CHANGE] [--format mermaid] [--scope active|archived|all] [--depth N]`（生成变更依赖图并输出到标准输出）

常见校验修复（TOON 风格）：

1) Main spec 缺少 YAML frontmatter（仅 main spec 需要）：
```markdown
---
llman_spec_valid_scope:
  - src
llman_spec_valid_commands:
  - llman sdd validate <feature-id> --type spec --strict --no-interactive
llman_spec_evidence:
  - <evidence>
---
```

2) Main spec 缺少 canonical ` ```toon ` payload（`llmanspec/specs/<feature-id>/spec.md`）：
```toon
kind: llman.sdd.spec
name: sample
purpose: "One-line overview."
requirements[1]{req_id,title,statement}:
  r1,Title,System MUST do something.
scenarios[1]{req_id,id,given,when,then}:
  r1,happy,"",a trigger happens,the outcome is observed
```

3) Change 缺少 delta ops：至少补一个 op + scenario（`llmanspec/changes/<change-id>/specs/<feature-id>/spec.md`）：
```toon
kind: llman.sdd.delta
ops[1]{op,req_id,title,statement,from,to,name}:
  add_requirement,r1,Title,System MUST do something.,null,null,null
op_scenarios[1]{req_id,id,given,when,then}:
  r1,happy,"",a trigger happens,the outcome is observed
```

4) 表格化行引号错误（"Expected N tabular row values, but got M"）：
值包含逗号、冒号或方括号时，必须用双引号包裹。
```toon
# 错误：statement 中的逗号被解析为分隔符
r1,title,System MUST do X, Y, and Z.

# 正确：用引号包裹包含逗号的值
r1,title,"System MUST do X, Y, and Z."
```

备注：
- `toon` 文件必须只有一个 ` ```toon ` fence。
- `null` 表示可选字段缺失。
- `toon` 为 experimental：跨风格迁移请使用显式的 `llman sdd convert`。


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

## Future 到执行的规划
- 将 `llmanspec/changes/<id>/future.md` 视为候选待办池，而不是静态备注。
- 审查 `Deferred Items`、`Branch Options`、`Triggers to Reopen`，并把每项归类为：
  - `now`（需要立即转化为可执行工作）
  - `later`（保留在 future.md，补充明确触发信号）
  - `drop`（移除或标记拒绝并说明原因）
- 对每个 `now` 项，产出明确落地路径：
  - 后续 change id（`add-...`、`update-...`、`refactor-...`）
  - 受影响 capability/spec 路径
  - 第一条可执行动作（`llman-sdd-propose`、`llman-sdd-new-change`、`llman-sdd-continue`、`llman-sdd-ff` 或 `llman-sdd-apply`）
- 保持可追溯性：在新 proposal/design/tasks 中引用来源 future 条目。
- 若存在高不确定性，先暂停并提问，再创建新变更工件。