---
name: "llman-sdd-specs-compact"
description: "压缩去重 specs：合并冗余 requirement/scenario，规范行为不变。仅用户明确要求时手动运行。"
metadata:
  version: "0.7.0"
---

# LLMAN SDD Specs Compact

在不改变规范行为的前提下压缩 specs。维护工具，不属于日常 pipeline，通常在归档积累较多后执行。

## Context
- specs 随变更积累膨胀，出现重复 requirement/scenario；压缩必须可验证、可回归。
- archive 历史过大时会干扰压缩评审与定位。

## Goal
- 合并冗余 requirement/scenario，形成更紧凑可维护的规范结构。

## Constraints
- 未经明确替代不得删除规范性行为；尽量保持 requirement 标题稳定；每个保留 requirement 至少一个有效 scenario。
- **改 `llmanspec/specs/**` 须走 change**：先绑定分支（`change start` / `attach`），在绑定分支上编辑提交；**禁止**在默认分支直接压缩改写。

## Workflow
1. 盘点 specs（`llman-sdd list --specs`）。
2. 归档历史较大时先 freeze：预览 `llman-sdd archive freeze --dry-run`；执行 `llman-sdd archive freeze --before <YYYY-MM-DD> --keep-recent <N>`。
3. 识别跨 capability 重叠（跨 specs 重复 req id：`llman-sdd project dedupe-req-ids --dry-run` 报告重映射计划）。
4. 产出压缩计划（canonical requirements + keep/merge/remove 决策 + 迁移说明）。
5. 执行并验证（`llman-sdd validate --specs --strict`）。

## Decision Policy
- 语义等价优先合并；仅引用关系清晰时提取共享文本；archive 噪声大时先 freeze 再压缩。
- 若压缩会改变外部行为，先暂停并询问用户。

## Output Contract
- 按 capability 分组的压缩方案：keep/merge/remove 决策及理由 + 验证命令与预期结果。

> 命令细节用 `llman-sdd <cmd> --help` 查看；命令参考以 CLI 为准，skill 不内嵌命令表。
> 文中「规约」= 本项目 `llmanspec/specs/` 下的 `.feature` 文件；用 `llman-sdd list --specs` / `llman-sdd show <capability>` 查全文。

校验修复（单轨 feature-as-spec）：

1）缺头注释（`missing # capability: header comment`）：每个 capability `.feature`（`llmanspec/specs/<capability>.feature` 或目录内同名主文件）必须以下列注释开头：
```
# language: zh-CN
# capability: <capability>
# purpose: 一句话概述
# scope: src/
```

2）原生分层格式（`rule must carry an @req:<req_id> tag on the rule header`）：
- 规范样式只有一种：`@req:<id>` 挂在 `规则:` 块头标签,块内嵌套 `场景:`(假如/当/那么)是可执行示例——默认首选。
- 仅当需求无法程序化表达或暂不转写时才保留无嵌套场景的 `规则:`(裸规则):描述自由文本,无 MUST/SHALL 强制;validate 以聚合计数提示,review `pending` 信号计量,specs-compact 负责压降。
- 历史标签 `@executable`/`@rule`/`@human`/`@manual` 不再使用、解析惰性;旧文件报结构问题时运行 `llman-sdd spec migrate-native` 迁移。
- 不在任何 `规则:` 内的顶层 `场景:` 是功能级示例:无规则句柄、不告警、不参与规则统计(Gherkin 原生语义)。

分支护栏：
- 先 `change start` / `attach` 绑定分支，再在绑定的非默认分支编辑 `.feature` 并 commit（落地 specs）。
- 锁定规则（报告制）：改/删既有 `规则:` 块只出 WARNING，不阻断 validate / finalize / `change diff`；报告按 `@req:<id>` 指明被改规则。控制点：git 分支对比 + `llman-sdd review` / `change diff`。旧锁定确认元数据（frontmatter `rules_touched` / `agent_acked`、`@agent` tag、`--yes` 确认语义）已全部删除，无别名无兼容层。
- `stage=full` 且 specs-landed 门通过（specsLanded ∨ `needs_specs_change: false`）即可进 apply；verify/finalize 须 `readyToImplement=true`（完成信号）。收口优先 `change finalize`。

## Ethics Governance
- `ethics.risk_level`：low——仅读写本仓库与 `llmanspec/`，无外发动作；正文另有声明时从其声明。
- `ethics.prohibited_actions`：违反正文「硬约束」的动作；未经用户明确要求的 push / PR / 外部上传。
- `ethics.required_evidence`：结论须有命令输出或文件路径佐证；门禁状态以 `llman-sdd validate` 为准。
- `ethics.refusal_contract`：门禁 CRITICAL 未清零 → 拒绝进入下一阶段；自修复达上限 → 报告 blocker。
- `ethics.escalation_policy`：改动 SDD 合约/模板或执行不可逆动作前，暂停并请用户确认。
