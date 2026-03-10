---
name: openspec-verify-change
description: Verify implementation matches change artifacts. Use when the user wants to validate that implementation is complete, correct, and coherent before archiving.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.2.0"
---

验证实现是否与变更工件(specs、tasks、design)一致.

**输入**:可选指定变更名称.如果省略,先判断是否可从对话上下文推断;若含糊或不明确,必须提示可用的变更.

**步骤**

1. **如果未提供变更名称,提示进行选择**

   运行 `openspec list --json` 以获取可用变更.使用 **AskUserQuestion 工具** 让用户选择.

   显示具有实施任务的变更(存在 tasks 工件).
   如可用,包含每个变更使用的 schema.
   将未完成任务的变更标记为“(进行中)”.

   **重要**:不要猜测或自动选择变更.始终让用户选择.

2. **检查状态以了解 schema**
   ```bash
   openspec status --change "<name>" --json
   ```
   解析 JSON 以了解:
   - `schemaName`:正在使用的工作流(例如 "spec-driven"、"tdd")
   - 该变更存在的工件

3. **获取变更目录并加载工件**

   ```bash
   openspec instructions apply --change "<name>" --json
   ```

   这会返回变更目录和上下文文件.从 `contextFiles` 读取所有可用工件.

4. **初始化验证报告结构**

   创建包含三个维度的报告结构:
   - **Completeness**:跟踪任务和规范覆盖
   - **Correctness**:跟踪需求实现和场景覆盖
   - **Coherence**:跟踪设计遵循和模式一致性

   每个维度可以有 CRITICAL、WARNING 或 SUGGESTION 问题.

5. **验证完整性**

   **任务完成情况**:
   - 如果 contextFiles 中存在 tasks.md,读取它
   - 解析复选框:`- [ ]`(未完成) vs `- [x]`(完成)
   - 统计完成数与总数
   - 如果存在未完成任务:
     - 为每个未完成任务添加 CRITICAL 问题
     - 推荐:"Complete task: <description>" 或 "Mark as done if already implemented"

   **规范覆盖**:
   - 如果 `openspec/changes/<name>/specs/` 中存在增量规范:
     - 提取所有需求(标记为 "### Requirement:")
     - 对每个需求:
       - 搜索代码库中与需求相关的关键词
       - 评估是否可能存在实现
     - 如果需求看起来未实现:
       - 添加 CRITICAL 问题:"Requirement not found: <requirement name>"
       - 推荐:"Implement requirement X: <description>"

6. **验证正确性**

   **需求实现映射**:
   - 对每个增量规范中的需求:
     - 搜索代码库中的实现证据
     - 如找到,记录文件路径和行范围
     - 评估实现是否符合需求意图
     - 如果发现偏差:
       - 添加 WARNING:"Implementation may diverge from spec: <details>"
       - 推荐:"Review <file>:<lines> against requirement X"

   **场景覆盖**:
   - 对每个增量规范中的场景(标记为 "#### Scenario:"):
     - 检查代码是否处理了条件
     - 检查是否存在覆盖该场景的测试
     - 如果场景看起来未覆盖:
       - 添加 WARNING:"Scenario not covered: <scenario name>"
       - 推荐:"Add test or implementation for scenario: <description>"

7. **验证一致性**

   **设计遵循**:
   - 如果 contextFiles 中存在 design.md:
     - 提取关键决策(查找 "Decision:"、"Approach:"、"Architecture:" 等部分)
     - 验证实现是否遵循这些决策
     - 如果发现矛盾:
       - 添加 WARNING:"Design decision not followed: <decision>"
       - 推荐:"Update implementation or revise design.md to match reality"
   - 如果没有 design.md:跳过设计遵循检查,并注明 "No design.md to verify against"

   **代码模式一致性**:
   - 检查新代码是否符合项目模式
   - 检查文件命名、目录结构、编码风格
   - 如果发现显著偏离:
     - 添加 SUGGESTION:"Code pattern deviation: <details>"
     - 推荐:"Consider following project pattern: <example>"

8. **生成验证报告**

   **Summary Scorecard**:
   ```
   ## Verification Report: <change-name>

   ### Summary
   | Dimension    | Status           |
   |--------------|------------------|
   | Completeness | X/Y tasks, N reqs|
   | Correctness  | M/N reqs covered |
   | Coherence    | Followed/Issues  |
   ```

   **Issues by Priority**:

   1. **CRITICAL** (Must fix before archive):
      - Incomplete tasks
      - Missing requirement implementations
      - Each with specific, actionable recommendation

   2. **WARNING** (Should fix):
      - Spec/design divergences
      - Missing scenario coverage
      - Each with specific recommendation

   3. **SUGGESTION** (Nice to fix):
      - Pattern inconsistencies
      - Minor improvements
      - Each with specific recommendation

   **Final Assessment**:
   - If CRITICAL issues: "X critical issue(s) found. Fix before archiving."
   - If only warnings: "No critical issues. Y warning(s) to consider. Ready for archive (with noted improvements)."
   - If all clear: "All checks passed. Ready for archive."

**Verification Heuristics**

- **Completeness**:聚焦客观检查项(复选框、需求列表)
- **Correctness**:使用关键词搜索、文件路径分析、合理推断——无需绝对确定
- **Coherence**:关注明显不一致,不吹毛求疵
- **False Positives**:不确定时,优先 SUGGESTION,其次 WARNING,再到 CRITICAL
- **Actionability**:每个问题都必须给出具体建议,并在可行时附文件/行号引用

**Graceful Degradation**

- 如果只有 tasks.md:仅验证任务完成情况,跳过规范/设计检查
- 如果有 tasks + specs:验证完整性和正确性,跳过设计
- 如果工件齐全:验证三个维度
- 始终说明跳过了哪些检查及原因

**Output Format**

使用清晰的 Markdown:
- Summary scorecard 表格
- 按优先级分组的问题列表 (CRITICAL/WARNING/SUGGESTION)
- 代码引用格式:`file.ts:123`
- 具体、可执行的建议
- 不要使用含糊建议,如 "consider reviewing"

