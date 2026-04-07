---
name: openspec-continue-change
description: Continue working on an OpenSpec change by creating the next artifact. Use when the user wants to progress their change, create the next artifact, or continue their workflow.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.2.0"
---

通过创建下一个工件来继续处理变更.

**输入**:可选择指定变更名称.如果省略,先判断是否可从对话上下文推断;若含糊或不明确,必须提示可用的变更.

**步骤**

1. **如果未提供变更名称,提示进行选择**

   运行 `openspec list --json` 以获取按最近修改排序的可用变更.然后使用 **AskUserQuestion 工具** 让用户选择要处理的变更.

	   将最近修改的 3-4 个变更显示为选项,显示:
	   - 变更名称
	   - Schema(若有 `schema` 字段则使用,否则为 "spec-driven")
	   - 状态(例如,"0/5 tasks"、"complete"、"no tasks")
	   - 修改时间(来自 `lastModified` 字段)

   将最近修改的变更标记为"(推荐)",因为这可能是用户想要继续的变更.

   **重要**:不要猜测或自动选择变更.始终让用户选择.

	2. **检查当前状态**
	   ```bash
	   openspec status --change "<name>" --json
	   ```
	   解析 JSON 以了解当前状态.输出包含:
	   - `schemaName`:正在使用的工作流 schema(例如,"spec-driven")
	   - `artifacts`:工件数组及其状态("done"、"ready"、"blocked")
	   - `isComplete`:是否所有工件都已完成

3. **根据状态采取行动**:

   ---

	   **如果所有工件都已完成(`isComplete: true`)**:
	   - 祝贺用户
	   - 显示最终状态(包含所用 schema)
	   - 建议:"所有工件已创建!你现在可以实施此变更或将其归档."
	   - 停止

   ---

	   **如果工件已准备好创建**(状态显示 `status: "ready"` 的工件):
	   - 从状态输出中选择第一个具有 `status: "ready"` 的工件
	   - 获取其说明:
	     ```bash
	     openspec instructions <artifact-id> --change "<name>" --json
	     ```
	   - 解析 JSON.关键字段包括:
	     - `context`:项目背景(对你是约束——不要输出到文件中)
	     - `rules`:工件规则(对你是约束——不要输出到文件中)
	     - `template`:输出文件的结构
	     - `instruction`:schema 特定指导
	     - `outputPath`:写入位置
	     - `dependencies`:已完成工件(用于阅读上下文)
	   - **创建工件文件**:
	     - 阅读任何已完成依赖工件文件以获取上下文
	     - 使用 `template` 作为结构,填写其各部分
	     - 写作时将 `context` 和 `rules` 作为约束,但不要把它们复制进文件
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
	- 使用的 schema 工作流
	- 当前进度(N/M 完成)
	- 现在解锁的工件
	- 提示:"想要继续吗？只需让我继续或告诉我下一步做什么."

	**工件创建指南**

	工件类型及其目的取决于 schema.使用 instructions 输出中的 `instruction` 字段来理解要创建什么.

	常见工件模式:

	**spec-driven schema** (proposal → specs → design → tasks):
	- **proposal.md**:若不清楚变更,先询问用户.填写 Why、What Changes、Capabilities、Impact.
	  - Capabilities 部分至关重要——列出的每个 capability 都需要一个规范文件.
	- **specs/<capability>/spec.md**:为 proposal 的 Capabilities 中列出的每个 capability 创建一个规范文件(用 capability 名称,不是 change 名称).
	- **design.md**:记录技术决策、架构与实现思路.
	- **tasks.md**:将实现拆分为带复选框的任务清单.

	其他 schema:以 CLI 输出中的 `instruction` 为准.

	**护栏**
	- 每次调用创建一个工件
	- 在创建新工件之前始终阅读依赖项工件
	- 永远不要跳过工件或乱序创建
	- 如果上下文不清楚,在创建之前询问用户
	- 在写入之前验证工件文件是否存在,然后再标记进度
	- 使用 schema 的工件顺序,不要假设固定工件名称
	- **重要**:`context` 和 `rules` 是给你的约束,不是文件内容
	  - 不要把 `<context>`, `<rules>`, `<project_context>` 块复制到工件中
	  - 它们用于指导你写作,但不应出现在输出里

