---
name: "llman-sdd-propose"
description: "创建 llman SDD 变更提案，一次性生成 proposal + delta specs + tasks 等规划工件。用于正式定义变更——尤其是涉及 MUST/SHALL 行为合约的变更。"
metadata:
  version: "0.0.61"
---

# LLMAN SDD 提案（Propose）

创建一个新变更，并一次性生成所有规划工件（proposal + delta specs + tasks；design 可选），然后执行校验并建议下一步动作。

## Pipeline 位置

```mermaid
flowchart LR
    explore["llman-sdd-explore<br/>探索"] --> propose
    propose["★ llman-sdd-propose ★<br/>提案（你现在在这里）"]
    propose --> apply["llman-sdd-apply<br/>实施"]
    apply --> verify["llman-sdd-verify<br/>验证"]
    verify --> archive["llman-sdd-archive<br/>归档"]

    style propose fill:#fff3cd,stroke:#ffc107,stroke-width:3px
```

> 📍 你现在在提案阶段 → 下一步 `llman-sdd-apply`（实施）
> 📎 如果只是小改动（不改行为合约），可直接 `llman-sdd-quick`（快速路径）

## 硬约束

- **必须与用户确认 change id 后再写文件**：不同变更的边界不能模糊。
- **delta specs 至少含一个 op + 一个 scenario**：否则验证不通过。
- **不要问「要不要继续」**：在 propose 阶段内一路执行到底，生成工件并校验。
- **若变更已存在**：STOP 并建议用户使用 `llman-sdd-apply` 或 `llman-sdd-continue`。

## 步骤

### 0) Preflight
- 读取 `llmanspec/config.yaml` 了解项目上下文、规则、locale。
- `llman sdd validate --all --strict --no-interactive`：确保当前工件状态干净。
  - 若预存错误，先停下报告（在脏工件上叠加新变更会导致级联错误）。
- **检查 spec valid_scope 完整性**：使用 `llman sdd list --specs --json` 列出所有 spec，然后对每个 spec 验证其 `valid_scope` 中的每个路径是否存在于磁盘上。若存在缺失的文件/目录，停下并建议更新 spec（从 `valid_scope` 中移除已删除的路径）。

### 1) 判断变更规模（triage）
   - **行为合约变更**（改 MUST/SHALL、改外部行为）→ 走完整 SDD 流程
   - **实现变更**（重构、typo、性能）→ 建议走快速路径，用 `llman-sdd-quick`
   - **元规范变更**（改 SDD 模板/流程）→ 必须走完整 SDD 流程
   - 不确定时走完整 SDD 流程（保守选择）
2. 使用 `llman sdd context --task "<目标>" --paths "<范围>"` 获取相关 specs。
   - 如果 context 不可用，运行 `llman sdd index rebuild`（默认 `pageindex`，无需模型）后继续。
3. 收集输入：
   - 变更的简要描述
   - change id（若未给出则推导；kebab-case，动词前缀：`add-`、`update-`、`remove-`、`refactor-`）
   - 受影响的 capability/capabilities（用于命名 `specs/<capability>/`）
   - 在写入任何文件前确认最终 id

### 2) 确保项目已初始化：
   - 必须存在 `llmanspec/`；若不存在，提示先运行 `llman sdd init`，然后 STOP。

### 3) 创建变更目录与工件
   - 创建 `llmanspec/changes/<change-id>/` 与 `llmanspec/changes/<change-id>/specs/`。
   - 若变更已存在，STOP 并建议使用 `llman-sdd-continue`。
   - `proposal.md`（Why / What Changes / Capabilities / Impact）
   - 为每个 capability 创建 `specs/<capability>/spec.toon`（每个文件一份独立的 TOON 文档）：
     - 建议优先通过 authoring helpers 生成，确保 TOON payload 规范：
       - `llman sdd delta skeleton <change-id> <capability>`
       - `llman sdd delta add-op ...`
       - `llman sdd delta add-scenario ...`
     - 至少包含一个 `add_requirement`/`modify_requirement` op（statement 必须含 MUST/SHALL），并且至少包含一行匹配的 op scenario
   - 仅在涉及权衡/迁移时创建 `design.md`
   - `tasks.md`：按顺序拆分为可勾选清单（包含校验命令）

### 4) 校验：
   ```bash
   llman sdd validate <change-id> --strict --no-interactive
   ```
   此步骤必须通过后才能继续。若出现 TOON 解析错误，需修复引号：表格化行中包含逗号/冒号/方括号的值必须用双引号包裹。

### 4a) BDD 模式检查——在决定 scenario 写法之前
- 读取 `llmanspec/config.yaml`。是否含 `bdd:` 段？
  - **是（BDD-on）**：按下方 4b 的 BDD-on 写作规则进行。
  - **否（BDD-off）**：如果本次变更涉及可执行的行为场景（用户会想实际运行的 Given/When/Then），**一次性 upfront 询问**：「本次变更似乎包含可执行行为。是否启用 BDD-on 模式，让场景能作为 `.feature` 文件被校验？（会在 `config.yaml` 添加 `bdd:` 段）」
    - **是**：展示要添加的确切 `bdd:` 段（`run_command` 按项目测试框架选——rstest-bdd 用 `cargo test --features bdd`，pytest-bdd 用 `pytest {feature_dir} -k {feature_name} -v`）。让用户确认或编辑后写入 `config.yaml`，再按 4b 规则继续。
    - **否**：按 BDD-off 写作继续（场景留在 TOON 内仅作文档；`feature` 字段被忽略）。
- **禁止静默添加 `bdd:` 段**——必须先询问。添加它会改变 `validate`/`index` 在整个项目的行为。

### 4b) BDD-on 模式——仅当 `config.yaml` 含 `bdd:` 段时
- `spec.toon` 是 BDD-on spec 的唯一真源（结构与 BDD-off 相同：`kind`/`name`/`purpose`/`valid_scope`/`requirements`/`scenarios`）。
- Scenario 含 `feature` 字段（默认 `true`）：`true` → 在 `solidify` 阶段可写入 `.feature`；`false` → 留在 TOON 内仅作文档。
- Delta 永远是纯 TOON（`ops` + `op_scenarios`）。propose 时不要创建 `.feature` delta 文件。
- `apply` 完成后运行 `llman sdd solidify <change-id>` 从 delta 的可执行 scenario 生成/更新 `.feature` 文件。
- `.feature` 是衍生工件——永远不要手动编辑。TOON `scenarios` 表是唯一真源。

### 5) 总结已创建内容，并建议下一步：
   - 进入实现阶段：`llman-sdd-apply`。
   - 若需要先理清思路：`llman-sdd-explore`。

> 💡 提案完成 → 下一步 `llman-sdd-apply` 进入实施阶段。

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