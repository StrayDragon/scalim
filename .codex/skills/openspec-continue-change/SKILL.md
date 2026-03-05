---
name: openspec-continue-change
description: Continue working on an OpenSpec change by creating the next artifact. Use when the user wants to progress their change, create the next artifact, or continue their workflow.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.1.1"
---

通过创建下一个工件来继续处理变更.

**输入**:可选择指定变更名称.如果省略,先判断是否可从对话上下文推断;若含糊或不明确,必须提示可用的变更.

**步骤**

1. **如果未提供变更名称,提示进行选择**

   运行 `openspec list --json` 以获取按最近修改排序的可用变更.然后使用 **AskUserQuestion 工具** 让用户选择要处理的变更.

   将最近修改的 3-4 个变更显示为选项,显示:
   - 变更名称
   - 状态(例如,"0/5 tasks"、"complete"、"no tasks")
   - 修改时间(来自 `lastModified` 字段)

   将最近修改的变更标记为"(推荐)",因为这可能是用户想要继续的变更.

   **重要**:不要猜测或自动选择变更.始终让用户选择.

2. **检查当前状态**
   ```bash
   openspec status --change "<name>" --json
   ```
   解析 JSON 以了解当前状态.

3. **根据状态采取行动**:

   ---

   **如果所有工件都已完成(`isComplete: true`)**:
   - 祝贺用户
   - 显示最终状态
   - 建议:"所有工件已创建!您现在可以实施此变更或将其归档."
   - 停止

   ---

   **如果工件已准备好创建**(状态显示 `status: "ready"` 的工件):
   - 从状态输出中选择第一个具有 `status: "ready"` 的工件
   - 获取其说明:
     ```bash
     openspec instructions <artifact-id> --change "<name>" --json
     ```
   - 解析 JSON 以获取模板、依赖项及其解锁的内容
   - **使用模板作为起点创建工件文件**:
     - 阅读任何完成的依赖项文件以获取上下文
     - 根据上下文和用户的目标填写模板
     - 写入说明中指定的输出路径
   - 显示创建的内容以及现在解锁的内容
   - 在创建一个工件后停止

   ---

   **如果没有工件准备就绪(全部被阻止)**:
   - 这不应该发生在有效的 schema 上
   - 显示状态并建议检查问题

4. **创建工件后,显示进度**
   ```bash
   openspec status --change "<name>"
   ```

**输出**

每次调用后,显示:
- 创建了哪个工件
- 当前进度(N/M 完成)
- 现在解锁的工件
- 提示:"想要继续吗？只需让我继续或告诉我下一步做什么."

**工件创建指南**

填写模板时:

- **proposal.md**:如果不清楚,请询问用户变更.填写 Why、What Changes、Capabilities、Impact.
  - **重要**:Capabilities 部分至关重要.在填写之前:
    - 检查 `openspec/specs/` 是否有现有功能
    - 列出具有 kebab-case 名称的新功能(例如,`user-auth`、`data-export`)
    - 列出需要规范更新的修改功能
  - 列出的每个功能都需要在下一阶段有相应的规范文件.
- **specs/*.md**:为提案中列出的每个功能创建一个规范.使用 `specs/<capability-name>/spec.md` 路径.
- **design.md**:记录技术决策、架构和实施方法.
- **tasks.md**:根据规范和设计将实施分解为带复选框的任务.

**护栏**
- 每次调用创建一个工件
- 在创建新工件之前始终阅读依赖项工件
- 永远不要跳过工件或乱序创建
- 如果上下文不清楚,在创建之前询问用户
- 在写入之前验证工件文件是否存在,然后再标记进度

