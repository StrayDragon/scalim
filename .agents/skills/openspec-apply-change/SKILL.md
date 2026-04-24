---
name: openspec-apply-change
description: Implement tasks from an OpenSpec change. Use when the user wants to start implementing, continue implementation, or work through tasks.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.2.0"
---

从 OpenSpec 变更实施任务.

**输入**:可选择指定变更名称.如果省略,先判断是否可从对话上下文推断;若含糊或不明确,必须提示可用的变更.

**步骤**

1. **选择变更**

   如果提供了名称,就使用它.否则:
   - 如果用户在对话中提到了变更,先从上下文推断
   - 若只有一个活动变更,自动选择
   - 若不明确,运行 `openspec list --json` 获取可用变更,并使用 **AskUserQuestion 工具** 让用户选择

   始终说明:"使用变更:<name>",并告知如何覆盖(例如 `/opsx:apply <other>`).

2. **检查状态以了解 schema**
   ```bash
   openspec status --change "<name>" --json
   ```
   解析 JSON 以了解:
   - `schemaName`:正在使用的工作流(例如,"spec-driven")
   - 哪个工件包含任务(通常 spec-driven 为 "tasks";其他 schema 以 status 输出为准)

3. **获取应用说明**

   ```bash
   openspec instructions apply --change "<name>" --json
   ```

   这返回:
   - 上下文文件路径(随 schema 而变,可能是 proposal/specs/design/tasks,也可能是 spec/tests/implementation/docs 等)
   - 进度(总计、完成、剩余)
   - 带状态的任务列表
   - 基于当前状态的动态说明

   **处理状态:**
   - 如果 `state: "blocked"`(缺少工件):显示消息,建议使用 openspec-continue-change
   - 如果 `state: "all_done"`:祝贺,建议归档
   - 否则:继续实施

4. **阅读上下文文件**

   阅读 apply instructions 输出中的 `contextFiles` 列出的文件.
   文件取决于正在使用的 schema:
   - **spec-driven**: proposal、specs、design、tasks
   - 其他 schema:以 CLI 输出为准

5. **显示当前进度**

   显示:
   - 正在使用的 schema
   - 进度:"N/M 任务完成"
   - 剩余任务概述
   - 来自 CLI 的动态说明

6. **实施任务(循环直到完成或被阻止)**

   对于每个待处理任务:
   - 显示正在处理的任务
   - 进行所需的代码更改
   - 保持更改最小化并专注于任务
   - 在 tasks.md 中标记任务完成:`- [ ]` → `- [x]`
   - 继续下一个任务

   **如果以下情况则暂停:**
   - 任务不清楚 → 请求澄清
   - 实施显示设计问题 → 建议更新工件
   - 遇到错误或阻止程序 → 报告并等待指导
   - 用户中断

7. **完成或暂停时,显示状态**

   显示:
   - 此会话完成的任务
   - 整体进度:"N/M 任务完成"
   - 如果全部完成:建议归档
   - 如果暂停:解释原因并等待指导

**实施期间输出**

```
## 实施:<change-name>(schema: <schema-name>)

正在处理任务 3/7:<task description>
[...implementation happening...]
✓ 任务完成

正在处理任务 4/7:<task description>
[...implementation happening...]
✓ 任务完成
```

**完成时输出**

```
## 实施完成

**变更:** <change-name>
**Schema:** <schema-name>
**进度:** 7/7 任务完成 ✓

### 此会话完成
- [x] 任务 1
- [x] 任务 2
...

所有任务完成!准备好归档此变更.
```

**暂停时输出(遇到问题)**

```
## 实施暂停

**变更:** <change-name>
**Schema:** <schema-name>
**进度:** 4/7 任务完成

### 遇到问题
<问题描述>

**选项:**
1. <选项 1>
2. <选项 2>
3. 其他方法

您想怎么做？
```

**护栏**
- 继续完成任务,直到完成或被阻止
- 在开始之前始终阅读上下文(specs、design)
- 如果任务模棱两可,在实施之前暂停并询问
- 如果实施显示问题,暂停并建议工件更新
- 保持代码更改最小化并局限于每个任务
- 在完成每个任务后立即更新任务复选框
- 在错误、阻止程序或要求不清楚时暂停 - 不要猜测
 - 使用 CLI 输出中的 contextFiles,不要假设固定文件名

**流畅工作流集成**

此技能支持"对变更的操作"模型:

- **可以随时调用**:在所有工件完成之前(如果 tasks.md 存在)、部分实施之后、与其他操作交错
- **允许工件更新**:如果实施显示设计问题,建议更新工件 - 不是阶段锁定的,灵活工作

