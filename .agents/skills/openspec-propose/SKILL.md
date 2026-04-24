---
name: openspec-propose
description: Propose a new change with all artifacts generated in one step. Use when the user wants to quickly describe what they want to build and get a complete proposal with design, specs, and tasks ready for implementation.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.2.0"
---

提出一个新变更——一步完成创建变更并生成所有工件.

我会创建一个 change,包含以下工件:
- proposal.md (做什么 & 为什么)
- design.md (怎么做)
- tasks.md (实施步骤)

准备开始实现时,运行 /opsx:apply

---

**输入**: 用户请求应包含变更名称(kebab-case)或对想要构建内容的描述.

**步骤**

1. **如果没有清晰输入,先问用户要做什么**

   使用 **AskUserQuestion 工具**(开放式,无预设选项)询问:
   > "你想要做哪个变更? 请描述你想构建或修复的内容."

   从描述中推导 kebab-case 名称(例如 "添加用户认证" → `add-user-auth`).

   **重要**: 在没有理解用户要做什么之前,不要继续.

2. **创建变更目录**
   ```bash
   openspec new change "<name>"
   ```
   这会在 `openspec/changes/<name>/` 下创建脚手架,包含 `.openspec.yaml`.

3. **获取工件构建顺序**
   ```bash
   openspec status --change "<name>" --json
   ```
   解析 JSON 获取:
   - `applyRequires`: 实施前必须完成的工件 ID 数组(例如 `["tasks"]`)
   - `artifacts`: 所有工件列表,包含状态和依赖关系

4. **按顺序创建工件,直到满足 apply 条件**

   使用 **TodoWrite 工具** 跟踪工件创建进度.

   按依赖顺序循环处理工件(优先处理没有未完成依赖的工件):

   a. **对每个状态为 `ready` 的工件(依赖已满足)**:
      - 获取说明:
        ```bash
        openspec instructions <artifact-id> --change "<name>" --json
        ```
      - 说明 JSON 包含:
        - `context`: 项目背景(对你是约束——不要写进输出文件)
        - `rules`: 工件规则(对你是约束——不要写进输出文件)
        - `template`: 输出结构模板
        - `instruction`: 该工件类型的 schema 指导
        - `outputPath`: 需要写入的路径
        - `dependencies`: 已完成、需要读取的依赖工件
      - 阅读已完成的依赖文件获取上下文
      - 以 `template` 为结构创建该工件文件
      - 将 `context`/`rules` 作为约束应用,但不要复制到文件中
      - 简要汇报进度:"Created <artifact-id>"

   b. **继续直到所有 `applyRequires` 工件完成**
      - 每创建一个工件后,重新运行 `openspec status --change "<name>" --json`
      - 检查 `applyRequires` 中每个 artifact ID 是否在 artifacts 列表里为 `status: "done"`
      - 当全部完成时停止

   c. **如果某个工件需要用户输入**(上下文不清晰):
      - 使用 **AskUserQuestion 工具** 澄清
      - 然后继续创建

5. **显示最终状态**
   ```bash
   openspec status --change "<name>"
   ```

**输出**

在完成所有工件后,总结:
- Change 名称及路径
- 已创建的工件列表及简要说明
- 就绪提示:"所有工件已创建! 已准备好实现."
- 引导:"运行 `/opsx:apply` 或让我直接实现,开始按照 tasks 工作."

**工件创建指南**

- 每个工件类型都遵循 `openspec instructions` 返回的 `instruction`
- Schema 定义了每个工件应包含的内容——按 schema 来写
- 在创建新工件前,先阅读依赖工件获取上下文
- 以 `template` 为输出结构——填充各个章节
- **重要**: `context` 和 `rules` 是给你的约束,不是文件内容
  - 不要把 `<context>`, `<rules>`, `<project_context>` 块复制进工件文件
  - 它们只用于指导你写作,不应出现在输出中

**护栏**
- 创建实现所需的全部工件(由 schema 的 `apply.requires` 定义)
- 在创建新工件前始终阅读依赖工件
- 如果关键上下文不清楚,询问用户——但优先做合理假设以保持推进
- 如果同名 change 已存在,询问用户是继续还是新建
- 写完每个工件后,验证文件存在再继续

