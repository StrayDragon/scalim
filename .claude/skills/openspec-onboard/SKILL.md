---
name: openspec-onboard
description: Guided onboarding for OpenSpec - walk through a complete workflow cycle with narration and real codebase work.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.2.0"
---

引导用户完成他们第一次完整的 OpenSpec 工作流闭环。这是一次教学型实践体验：你会在用户真实代码库中做真实工作，并在过程中解释每一步。

---

## 前置检查

开始前，先检查 OpenSpec CLI 是否已安装：

```bash
# Unix/macOS
openspec --version 2>&1 || echo "CLI_NOT_INSTALLED"
# Windows (PowerShell)
# if (Get-Command openspec -ErrorAction SilentlyContinue) { openspec --version } else { echo "CLI_NOT_INSTALLED" }
```

**如果 CLI 未安装：**
> 尚未安装 OpenSpec CLI。请先安装，然后再回来运行 `/opsx:onboard`。

若未安装，到此停止。

---

## 阶段 1：欢迎

展示：

```
## 欢迎使用 OpenSpec！

我会带你走一遍完整变更周期：从想法到实现，基于你代码库中的一个真实任务。你会通过“边做边学”的方式掌握工作流。

**我们会做什么：**
1. 在你的代码库中选一个小而真实的任务
2. 先做一次简短探索
3. 创建 change（承载这次工作的容器）
4. 产出工件：proposal → specs → design → tasks
5. 按 tasks 完成实现
6. 归档完成后的 change

**时间：**约 15-20 分钟

我们先从找一个可做的任务开始。
```

---

## 阶段 2：任务选择

### 代码库分析

扫描代码库，寻找小型改进机会。重点看：

1. **TODO/FIXME 注释** - 在代码文件中搜索 `TODO`、`FIXME`、`HACK`、`XXX`
2. **缺失错误处理** - 吞掉错误的 `catch` 块，或缺少 try-catch 的高风险操作
3. **缺少测试的函数** - 交叉查看 `src/` 与测试目录
4. **类型问题** - TypeScript 中的 `any`（`: any`、`as any`）
5. **调试残留** - 非调试代码中的 `console.log`、`console.debug`、`debugger`
6. **缺失校验** - 用户输入处理缺少校验

同时查看最近 Git 活动：
```bash
# Unix/macOS
git log --oneline -10 2>/dev/null || echo "No git history"
# Windows (PowerShell)
# git log --oneline -10 2>$null; if ($LASTEXITCODE -ne 0) { echo "No git history" }
```

### 给出建议

基于你的分析，给出 3-4 条具体建议：

```
## 任务建议

根据对代码库的扫描，这里有几项适合入门的任务：

**1. [最有价值的任务]**
   位置：`src/path/to/file.ts:42`
   范围：约 1-2 个文件，20-30 行
   适合原因：[简短说明]

**2. [第二个任务]**
   位置：`src/another/file.ts`
   范围：约 1 个文件，15 行
   适合原因：[简短说明]

**3. [第三个任务]**
   位置：[location]
   范围：[estimate]
   适合原因：[简短说明]

**4. 其他想法？**
   你也可以直接告诉我你想做什么。

你对哪个任务更感兴趣？（选序号或直接描述）
```

**如果没找到明显候选：** 回退为直接询问用户要做什么：
> 我没有在你的代码库里发现明显的“快速收益”点。有没有一个你一直想补上或修掉的小问题？

### 范围护栏

如果用户选择或描述的任务过大（大型功能、多日工作）：

```
这个任务很有价值，但对第一次 OpenSpec 实操来说可能偏大。

为了学习工作流，小一点更好：你可以完整看到闭环，而不是卡在实现细节里。

**可选项：**
1. **先切小** - [该任务] 最小可交付的一块是什么？例如先做 [具体切片]？
2. **换一个任务** - 从上面建议里再选一个，或给一个新的小任务
3. **仍按原计划做** - 如果你确实想做，我们也可以继续，只是会更久

你更倾向哪种？
```

如果用户坚持，允许继续。这是软护栏，不是硬限制。

---

## 阶段 3：Explore 演示

当任务确定后，先简短演示 explore 模式：

```
在创建 change 之前，我先快速演示一下 **explore 模式**——它用于在承诺方案前把问题想清楚。
```

花 1-2 分钟调查相关代码：
- 阅读相关文件
- 如果有帮助，画一个 ASCII 小图
- 记录关键考虑点

```
## 快速探索

[你的简短分析：你看到了什么、有哪些注意点]

┌─────────────────────────────────────────┐
│   [可选：如有帮助可放 ASCII 图]          │
└─────────────────────────────────────────┘

Explore 模式（`/opsx:explore`）就用于这种思考：先调查、再实现。你在任何需要理清问题的时候都可以用。

接下来我们创建一个 change 来承载这次工作。
```

**PAUSE** - 等待用户确认后再继续。

---

## 阶段 4：创建 Change

**EXPLAIN：**
```
## 创建 Change

在 OpenSpec 里，"change" 是承载某项工作的思考和规划容器。它位于 `openspec/changes/<name>/`，包含 proposal、specs、design、tasks 等工件。

我先为当前任务创建一个。
```

**DO：** 使用推导出的 kebab-case 名称创建 change：
```bash
openspec new change "<derived-name>"
```

**SHOW：**
```
已创建：`openspec/changes/<name>/`

目录结构如下：
```
openspec/changes/<name>/
├── proposal.md    ← 为什么做（空，待填写）
├── design.md      ← 如何做（空）
├── specs/         ← 详细需求（空）
└── tasks.md       ← 实施清单（空）
```

现在我们先填第一个工件：proposal。
```

---

## 阶段 5：Proposal

**EXPLAIN：**
```
## Proposal

proposal 记录这次变更**为什么要做**，以及高层面上**要做什么**。它是这项工作的“电梯陈述”。

我会基于当前任务先起一个草稿。
```

**DO：** 起草 proposal 内容（先不保存）：

```
这是 proposal 草稿：

---

## Why

[1-2 句说明问题/机会]

## What Changes

[列出会发生哪些变化]

## Capabilities

### New Capabilities
- `<capability-name>`: [简要说明]

### Modified Capabilities
<!-- If modifying existing behavior -->

## Impact

- `src/path/to/file.ts`: [会改什么]
- [如果有其他文件也列出]

---

这个草稿是否准确表达了意图？保存前我可以先调整。
```

**PAUSE** - 等待用户确认/反馈。

确认后保存 proposal：
```bash
openspec instructions proposal --change "<name>" --json
```
然后写入 `openspec/changes/<name>/proposal.md`。

```
Proposal 已保存。这是你的“why”文档，后续理解变化时也可以随时回头完善。

下一步：specs。
```

---

## 阶段 6：Specs

**EXPLAIN：**
```
## Specs

specs 用精确、可测试的方式定义我们要构建的**what**。它采用 requirement/scenario 格式，让预期行为可验证。

像这类小任务，通常一个 spec 文件就够。
```

**DO：** 创建 spec 文件：
```bash
# Unix/macOS
mkdir -p openspec/changes/<name>/specs/<capability-name>
# Windows (PowerShell)
# New-Item -ItemType Directory -Force -Path "openspec/changes/<name>/specs/<capability-name>"
```

起草 spec 内容：

```
这是 spec：

---

## ADDED Requirements

### Requirement: <Name>

<Description of what the system should do>

#### Scenario: <Scenario name>

- **WHEN** <trigger condition>
- **THEN** <expected outcome>
- **AND** <additional outcome if needed>

---

这种 WHEN/THEN/AND 格式让需求具备可测试性，本质上可以直接映射为测试用例。
```

保存到 `openspec/changes/<name>/specs/<capability>/spec.md`。

---

## 阶段 7：Design

**EXPLAIN：**
```
## Design

design 记录我们将如何实现（how）：技术决策、权衡与方案。

对于小变更，设计文档可以很短。这完全没问题，不是每个变更都需要深度架构讨论。
```

**DO：** 起草 design.md：

```
这是 design：

---

## Context

[当前状态的简要背景]

## Goals / Non-Goals

**Goals:**
- [我们要达成什么]

**Non-Goals:**
- [明确不做什么]

## Decisions

### Decision 1: [关键决策]

[说明方案与理由]

---

对于小任务，这种粒度足够表达关键决策，同时避免过度设计。
```

保存到 `openspec/changes/<name>/design.md`。

---

## 阶段 8：Tasks

**EXPLAIN：**
```
## Tasks

最后，我们把工作拆成可执行任务：这些复选框会驱动 apply 阶段。

任务应当小、明确，并按合理顺序排列。
```

**DO：** 基于 specs 与 design 生成 tasks：

```
这里是实施任务：

---

## 1. [分类或文件]

- [ ] 1.1 [具体任务]
- [ ] 1.2 [具体任务]

## 2. Verify

- [ ] 2.1 [验证步骤]

---

每个复选框都是 apply 阶段的一个工作单元。准备开始实现了吗？
```

**PAUSE** - 等待用户确认准备进入实现。

保存到 `openspec/changes/<name>/tasks.md`。

---

## 阶段 9：Apply（实现）

**EXPLAIN：**
```
## 实现

现在我们逐项实现任务，并在完成后勾选。我会在每步开始时提示当前任务，并偶尔说明 specs/design 如何影响实现。
```

**DO：** 对每个任务执行：

1. 宣告：“正在处理任务 N：[描述]”
2. 在代码库中实现改动
3. 自然引用 specs/design：“spec 要求 X，因此这里做 Y”
4. 在 tasks.md 标记完成：`- [ ]` → `- [x]`
5. 简短状态：“✓ 任务 N 完成”

讲解保持轻量，不逐行说教。

所有任务完成后：

```
## 实现完成

全部任务已完成：
- [x] Task 1
- [x] Task 2
- [x] ...

变更已实现！还差最后一步：归档。
```

---

## 阶段 10：Archive

**EXPLAIN：**
```
## 归档

当 change 完成后，我们会进行归档。它会从 `openspec/changes/` 移动到 `openspec/changes/archive/YYYY-MM-DD-<name>/`。

归档后的 change 会成为项目决策历史，后续你可以回溯“为什么当时这样实现”。
```

**DO：**
```bash
openspec archive "<name>"
```

**SHOW：**
```
已归档到：`openspec/changes/archive/YYYY-MM-DD-<name>/`

该 change 已进入项目历史。代码已落地，决策记录也被保留。
```

---

## 阶段 11：回顾与下一步

```
## 恭喜！

你刚刚完成了一次完整 OpenSpec 周期：

1. **Explore** - 思考并澄清问题
2. **New** - 创建 change 容器
3. **Proposal** - 明确 WHY
4. **Specs** - 细化 WHAT
5. **Design** - 决定 HOW
6. **Tasks** - 拆解执行步骤
7. **Apply** - 实施改动
8. **Archive** - 保留决策记录

同样的节奏适用于任意规模的变更：小修复或大功能都可以。

---

## 命令参考

| Command | 作用 |
|---------|------|
| `/opsx:explore` | 在工作前/中思考问题 |
| `/opsx:new` | 新建 change，逐步创建工件 |
| `/opsx:ff` | 快速前进：一次性生成全部工件 |
| `/opsx:continue` | 继续推进已有 change |
| `/opsx:apply` | 按 change 的 tasks 实施 |
| `/opsx:verify` | 验证实现是否匹配工件 |
| `/opsx:archive` | 归档完成的 change |

---

## 接下来

试试对一个你真正想做的事情使用 `/opsx:new` 或 `/opsx:ff`。你已经掌握节奏了。
```

---

## 友好退出处理

### 用户希望中途停止

如果用户表示需要暂停、稍后继续，或明显不想继续：

```
没问题！你的 change 已保存在 `openspec/changes/<name>/`。

之后想继续可以用：
- `/opsx:continue <name>` - 继续创建工件
- `/opsx:apply <name>` - 如果 tasks 已就绪，直接进入实现

工作不会丢失。你准备好时随时回来。
```

友好收尾，不施压。

### 用户只想看命令参考

如果用户表示只想看命令、跳过教程：

```
## OpenSpec 快速参考

| Command | 作用 |
|---------|------|
| `/opsx:explore` | 思考问题（不改业务代码） |
| `/opsx:new <name>` | 新建 change，逐步推进 |
| `/opsx:ff <name>` | 快速前进：一次性工件 |
| `/opsx:continue <name>` | 继续已有 change |
| `/opsx:apply <name>` | 实施任务 |
| `/opsx:verify <name>` | 验证实现 |
| `/opsx:archive <name>` | 完成后归档 |

可以从 `/opsx:new` 开始你的第一次 change；如果想更快，使用 `/opsx:ff`。
```

友好收尾。

---

## 护栏

- **在关键节点遵循 EXPLAIN → DO → SHOW → PAUSE**（探索后、proposal 草稿后、tasks 后、archive 后）
- **实现阶段保持轻讲解**，教学但不过度说教
- **不要跳过阶段**，即使变更很小，onboarding 目标仍是完整闭环
- **在标记点暂停确认**，但避免过度频繁打断
- **退出要体面**，绝不强迫用户继续
- **使用真实代码库任务**，不要模拟或虚构例子
- **温和控制范围**，优先引导小任务，同时尊重用户选择

