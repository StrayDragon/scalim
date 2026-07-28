---
name: "llman-sdd-verify"
description: "验证已实施的 llman SDD 变更是否与 specs/design/tasks 一致。产出分级报告（CRITICAL / WARNING / SUGGESTION），对比代码与工件。在 apply 完成后运行；全绿则可归档。"
metadata:
  version: "0.0.65"
  llman_sdd:
    bdd_mode: "off"
    skill_set: "default"
---

# LLMAN SDD Verify

使用此 skill 验证实现是否与该 change 的 artifacts 一致。

## Pipeline 位置

```mermaid
flowchart LR
    apply["llman-sdd-apply<br/>实施"] --> verify
    verify["★ llman-sdd-verify ★<br/>验证（你现在在这里）"]
    verify --> archive["llman-sdd-archive<br/>归档"]
    archive --> commit["git commit<br/>完成闭环"]

    style verify fill:#fff3cd,stroke:#ffc107,stroke-width:3px
```

> 📍 你现在在验证阶段 → 通过后下一步 `llman-sdd-archive`（归档）；失败则回到 `llman-sdd-apply`（修复）

## 硬约束

- **必须先通过 apply 阶段全绿**：未完成实现的 change 跳过验证。
- **CRITICAL 必须修复**：标记为 CRITICAL 的问题归档前必须修复。
- **不要问「要不要继续」**：跑完整个验证流程，输出完整报告。

## 步骤
1. 确定 change id（不明确时让用户从 `llman sdd list --json` 选择）。
2. 检查阶段守卫（权威）：
   ```bash
   stage=$(llman sdd show <id> --json --type change | jq -r .stage)
   ```
   （若无 `jq`，可用任意工具从 JSON 中解析 `stage` 值。）
   - 若 `stage` 不为 `full`，变更尚未实现、无可验证内容 → 必须停止并给出守卫提示：
     - `draft`："变更 <id> 是 draft 提案（仅 proposal.md），尚无可验证的实现。请先用 llman-sdd-propose 生成完整工件，再 `llman sdd change start <id>`，然后用 llman-sdd-apply 实现。" 若已有 proposal+design+tasks 仍是 `draft`，意味着变更**未 start/attach** —— 修复方式是 `llman sdd change start <id>` 或 `change attach <id>`（而非新增 `changes/<id>/specs/`）。
     - `designed`："变更 <id> 处于 designed 阶段，尚未进入 Full。请运行 `llman sdd change start <id>` 后再 apply/verify。"
3. 先跑一个快速校验门禁：
   - `llman sdd validate <id> --strict --no-interactive`
   - **诊断结构问题（Gherkin 解析 / `@req` 链接 / 双写 / 全局 req_id 唯一性）时优先加 `--no-check`**（BDD-on 下跳过可能耗时的 `bdd.run_command`），结构门禁全绿后再跑完整 `--check`（full mode）。`FAIL <item_type>/<id>` 行会逐条列出失败项（在 Totals 行上方）。
4. 阅读：

   - `llmanspec/changes/<id>/specs/` 下的 delta specs
   - `proposal.md` 与 `design.md`（如存在）
   - `tasks.md`（理解实现范围）

5. **双轴审查（标准轴 + 合约轴分离，互不掩盖）**——对比 diff（`git diff <merge-base>...HEAD`，merge-base 取 attach 的 base_sha 或 `main`）分两轴：
   - **合约轴（Spec）**：实现是否满足 `spec.toon` 的 MUST/SHALL 与 `*.feature` 的 GWT。
     - 缺失/部分实现的行为、错误实现、以及 diff 中未被 spec 要求的超范围改动。
     - 给出最小修复建议，或建议更新 artifacts。
   - **标准轴（Standards）**：代码是否符合 `AGENTS.md` 的编码规范 + 常见代码坏味（code smell）清单。
     - **权威优先级**：`AGENTS.md` 文档规范 > 坏味清单（文档说了算）；工具已强制的项跳过。
     - 坏味标记为**判断性提示**（「可能是 Feature Envy」），不是硬性违规。
     - 坏味清单（每项「是什么 → 怎么修」）：Mysterious Name（名不达意→重命名）/ Duplicated Code（重复逻辑→抽取共享）/ Feature Envy（方法更爱用别人的数据→移过去）/ Data Clumps（同组字段到处走→打包成类型）/ Primitive Obsession（原始类型充当领域概念→给专门类型）/ Repeated Switches（同类 switch 反复出现→多态或共享 map）/ Shotgun Surgery（一处改动散落多处→聚到一模块）/ Divergent Change（一文件因多无关原因被改→拆分）/ Speculative Generality（为未发生的需求加抽象→删除）/ Message Chains（长链 a.b().c()→隐藏于一方法）/ Middle Man（只转发→删掉直连）/ Refused Bequest（子类拒绝大部继承→改组合）。
   - 两轴可并行（sub-agent）审查；报告 MUST 分离呈现，MUST NOT 合并或交叉重排（一轴通过不能掩盖另一轴失败）。
6. **BDD-on 验证（Git-native Partitioned SSOT）**——仅当 `config.yaml` 含 `bdd:` 段时：
   - 确认 change 已 attach，且当前在对应 feature 分支上。
   - `llman sdd validate --specs`：Gherkin + `@req`/双写门禁；默认跑 `bdd.run_command`（可用 `--no-check` 跳过）。
   - 可选只读审查：`llman sdd change diff <id>`（或 `--export-patch <path>`）。diff 仅作审查/导出——绝不当作 apply 步骤。
   - 归档：**优先** `llman sdd change finalize <id>`（可不要求干净树；随后一次 `git commit`）；需要严格 `checkpoint_sha` 时再走 `checkpoint` → `archive`。
   - 检查：可执行 GWT 只在 live `.feature`；`morphology.dualWriteCount` 应为 0；若已有活跃 `*.feature.delta.toon` 则先迁移（不要自创 solidify/找补步骤）。

7. 输出简短报告：
   - **CRITICAL**（归档前必须修复）
   - **WARNING**（建议修复）
   - **SUGGESTION**（可选优化）
8. 若存在 CRITICAL，建议用 `llman-sdd-apply` 修复；若通过则建议归档：`llman sdd change finalize <id>`（推荐）或 fallback `checkpoint` + `archive`。

> 💡 验证通过 → 下一步 `llman-sdd-archive`（归档）；有 CRITICAL → 回到 `llman-sdd-apply`（修复）

行动前先阅读 `llmanspec/config.yaml`，并遵循其中的 `context` 与 `rules`（若有）。

常用命令：
- `llman sdd context --task "<描述>" --paths "<文件>"`（找相关 specs）。使用 pageindex agentic tree 后端（需 `LLMAN_SDD_INDEX_CHAT_MODEL`）。可用 `LLMAN_SDD_INDEX_BACKEND` 预设。
- `llman sdd list`（列出变更）
- `llman sdd list --specs`（列出 specs 及 purpose/scope 元数据）
- `llman sdd show <id>`（展示 change/spec）
- `llman sdd validate <id>`（校验 change 或 spec）
- `llman sdd validate --all`（批量校验）
- `llman sdd index rebuild`（重建 pageindex 树索引——不需要模型）
- `llman sdd index check`（检查索引新鲜度）
- `llman sdd change new <id>`（创建草稿 `changes/<id>/proposal.md`）
- `llman sdd change start <id> [--worktree]`（Designed→Full：干净树 → 创建 `sdd/<id>` 分支 + attach 绑定）
- `llman sdd change attach <id> [--force]`（绑定已有 feature 分支 + base SHA）
- `llman sdd change finalize <id> [--no-check]`（**推荐单 commit 路径**——不要求干净树；门禁 + 自动 ff-merge + 文档改名）
- `llman sdd change checkpoint <id> [--no-check]`（干净工作区 + 归档前门禁；严格 sha = HEAD）
- `llman sdd change diff <id> [--export-patch <path>]`（只读 `base...HEAD` 审查/导出）
- `llman sdd change archive <id>`（封存变更：自动 ff-merge 到默认分支，再将文档改名到 `changes/archive/`；单 commit 收尾优先用 `finalize`）
- `llman sdd archive freeze [--before YYYY-MM-DD] [--keep-recent N] [--dry-run]`（冻结已归档目录）
- `llman sdd archive thaw [--change <id> ...] [--dest <path>]`（从冷备份恢复）
- `llman sdd graph [CHANGE] [--format mermaid] [--scope active|archived|all] [--depth N]`（生成变更依赖图）
- `llman sdd project migrate [--kind format|partitioned|legacy-bdd|auto]`（一次性迁移）

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
