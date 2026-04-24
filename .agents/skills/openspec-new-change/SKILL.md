---
name: openspec-new-change
description: Start a new OpenSpec change using the experimental artifact workflow. Use when the user wants to create a new feature, fix, or modification with a structured step-by-step approach.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.2.0"
---

使用实验性驱动工件的方法开始新变更.

**输入**:用户的请求应包含变更名称(kebab-case)或他们想要构建的内容的描述.

**步骤**

1. **如果未提供明确的输入,询问他们想要构建什么**

   使用 **AskUserQuestion 工具**(开放式,无预设选项)询问:
   > "您想要进行什么变更？描述您想要构建或修复的内容."

   从他们的描述中,派生一个 kebab-case 名称(例如,"add user authentication" → `add-user-auth`).

   **重要**:在了解用户想要构建什么之前,请勿继续.

2. **确定工作流 schema**

   除非用户明确要求使用其他工作流,否则使用默认 schema(省略 `--schema`).

   **只有当用户提到以下内容时才使用其他 schema:**
   - "tdd" 或 "test-driven" → 使用 `--schema tdd`
   - 某个具体 schema 名称 → 使用 `--schema <name>`
   - "show workflows" 或 "what workflows" → 运行 `openspec schemas --json` 并让他们选择

   **否则**:省略 `--schema` 以使用默认值.

3. **创建变更目录**
   ```bash
   openspec new change "<name>"
   ```
   只有当用户请求特定工作流时才添加 `--schema <name>`.
   这将在 `openspec/changes/<name>/` 处创建脚手架变更,并使用所选 schema.

4. **显示工件状态**
   ```bash
   openspec status --change "<name>"
   ```
   这显示需要创建哪些工件以及哪些工件已准备就绪(依赖项已满足).

5. **获取第一个工件的说明**
   第一个工件取决于 schema(例如,spec-driven 为 `proposal`,tdd 为 `spec`).
   查看 status 输出,找到状态为 "ready" 的第一个工件.
   ```bash
   openspec instructions <first-artifact-id> --change "<name>"
   ```
   这将输出用于创建第一个工件的模板和上下文.

6. **停止并等待用户指示**

**输出**

完成步骤后,总结:
- 变更名称和位置
- 使用的 schema/工作流及其工件序列
- 当前状态(0/N 工件完成)
- 第一个工件的模板
- 提示:"准备好创建第一个工件了吗？只需描述此变更的内容,我将起草它,或者让我继续."

**护栏**
- 尚未创建任何工件 - 仅显示说明
- 不要超过显示第一个工件模板
- 如果名称无效(不是 kebab-case),请询问有效的名称
- 如果该名称的变更已存在,建议继续该变更
- 如果使用非默认工作流,请传递 `--schema`

