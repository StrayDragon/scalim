---
name: openspec-ff-change
description: Fast-forward through OpenSpec artifact creation. Use when the user wants to quickly create all artifacts needed for implementation without stepping through each one individually.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.1.1"
---

快速推进工件创建——一次性生成开始实施所需的一切.

**输入**:用户请求应包含变更名称(kebab-case),或对其想要构建内容的描述.

**步骤**

1. **如果未提供清晰的输入,询问要构建什么**

   使用 **AskUserQuestion 工具**(开放式,无预设选项)询问:
   > "你想要处理什么变更？描述你想构建或修复的内容."

   根据描述派生 kebab-case 名称(例如 "add user authentication" → `add-user-auth`).

   **重要**:在理解用户想构建什么之前不要继续.

2. **创建变更目录**
   ```bash
   openspec new change "<name>"
   ```
   这会在 `openspec/changes/<name>/` 创建一个脚手架变更.

3. **获取工件构建顺序**
   ```bash
   openspec status --change "<name>" --json
   ```
   解析 JSON 以获得:
   - `applyRequires`:实施前所需的工件 ID 数组(例如 `["tasks"]`)
   - `artifacts`:所有工件及其状态和依赖

4. **按顺序创建工件,直到可实施**

   使用 **TodoWrite 工具** 跟踪工件进度.

   按依赖顺序循环工件(先处理没有未满足依赖的工件):

   a. **对每个处于 `ready` 的工件(依赖已满足)**:
      - 获取说明:
        ```bash
        openspec instructions <artifact-id> --change "<name>" --json
        ```
      - 说明 JSON 包含:
        - `template`:要使用的模板内容
        - `instruction`:该工件类型的 schema 指导
        - `outputPath`:写入位置
        - `dependencies`:需要读取的已完成工件
      - 读取已完成依赖文件获取上下文
      - 按 schema 的 `instruction` 创建工件文件
      - 简短展示进度:"✓ 已创建 <artifact-id>"

   b. **持续直到 `applyRequires` 全部完成**
      - 每创建一个工件后,重新运行 `openspec status --change "<name>" --json`
      - 检查 `applyRequires` 中的每个工件 ID 在 artifacts 数组里是否为 `status: "done"`
      - 当所有 `applyRequires` 工件完成后停止

   c. **如果工件需要用户输入**(上下文不清晰):
      - 使用 **AskUserQuestion 工具** 澄清
      - 然后继续创建

5. **显示最终状态**
   ```bash
   openspec status --change "<name>"
   ```

**输出**

完成所有工件后,总结:
- 变更名称与位置
- 已创建工件列表(简短描述)
- 当前就绪情况:"所有工件已创建!可以开始实施."
- 提示:"运行 `/opsx:apply` 或让我开始实现来处理任务."

**工件创建指南**

- 对每种工件类型遵循 `openspec instructions` 返回的 `instruction`
- schema 定义了每个工件应包含什么——遵循它
- 在创建新工件之前先读依赖工件
- 使用 `template` 作为起点,并根据上下文填充

**护栏**
- 创建实施所需的全部工件(由 schema 的 `apply.requires` 定义)
- 在创建新工件之前始终阅读依赖工件
- 如果上下文关键不清晰,询问用户——但尽量做出合理判断以保持进度
- 如果已存在同名变更,建议继续该变更
- 写入后确认工件文件存在再继续

