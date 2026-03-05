---
name: openspec-bulk-archive-change
description: Archive multiple completed changes at once. Use when archiving several parallel changes.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.1.1"
---

一次操作归档多个已完成的变更.

该技能允许你批量归档变更,并通过检查代码库来判断实际实现,从而智能处理规范冲突.

**输入**:无需输入(会提示选择)

**步骤**

1. **获取活动中的变更**

   运行 `openspec list --json` 获取所有活动中的变更.

   如果没有活动中的变更,告知用户并停止.

2. **提示选择变更**

   使用 **AskUserQuestion 工具** 的多选让用户选择变更:
   - 显示每个变更及其 schema
   - 提供“所有变更”选项
   - 允许任意数量的选择(1+ 可用,2+ 更常见)

   **重要**:不要自动选择.始终让用户选择.

3. **批量校验 - 收集所有选定变更的状态**

   对每个选定变更,收集:

   a. **工件状态** - 运行 `openspec status --change "<name>" --json`
      - 解析 `schemaName` 与 `artifacts` 列表
      - 标注哪些工件为 `done`,哪些为其他状态

   b. **任务完成情况** - 读取 `openspec/changes/<name>/tasks.md`
      - 统计 `- [ ]`(未完成)与 `- [x]`(完成)
      - 如无 tasks 文件,标注为“无任务”

   c. **delta 规范** - 检查 `openspec/changes/<name>/specs/` 目录
      - 列出存在的能力规范
      - 对每个规范,提取需求名称(匹配 `### Requirement: <name>` 的行)

4. **检测规范冲突**

   构建 `capability -> [触及该能力的变更]` 的映射:

   ```
   auth -> [change-a, change-b]  <- 冲突(2+ 变更)
   api  -> [change-c]            <- OK(仅 1 个变更)
   ```

   当 2+ 个变更对同一能力有 delta 规范时视为冲突.

5. **智能解决冲突**

   **针对每个冲突**,调查代码库:

   a. **读取冲突变更的 delta 规范**,理解各自声称新增/修改的内容

   b. **在代码库中搜索实现证据**:
      - 查找与各自需求相关的实现代码
      - 检查相关文件、函数或测试

   c. **确定处理方案**:
      - 仅一个变更已实现 -> 仅同步该变更的规范
      - 两个都已实现 -> 按时间顺序应用(先旧后新,新覆盖旧)
      - 都未实现 -> 跳过规范同步并警告

   d. **记录每个冲突的解决方案**:
      - 应用哪个变更的规范
      - 应用顺序(如两者都实现)
      - 依据(代码库中的发现)

6. **显示汇总状态表**

   展示所有变更的汇总表:

   ```
   | Change               | Artifacts | Tasks | Specs   | Conflicts | Status |
   |---------------------|-----------|-------|---------|-----------|--------|
   | schema-management   | Done      | 5/5   | 2 delta | None      | Ready  |
   | project-config      | Done      | 3/3   | 1 delta | None      | Ready  |
   | add-oauth           | Done      | 4/4   | 1 delta | auth (!)  | Ready* |
   | add-verify-skill    | 1 left    | 2/5   | None    | None      | Warn   |
   ```

   对冲突展示解决方案:
   ```
   * 冲突解决方案:
     - auth 规范:将先应用 add-oauth,再应用 add-jwt(两者已实现,按时间顺序)
   ```

   对未完成变更展示警告:
   ```
   警告:
   - add-verify-skill:1 个工件未完成,3 个任务未完成
   ```

7. **确认批量操作**

   使用 **AskUserQuestion 工具** 进行单次确认:

   - “归档 N 个变更？”并根据状态提供选项
   - 选项可能包括:
     - “归档全部 N 个变更”
     - “仅归档 N 个就绪变更(跳过未完成)”
     - “取消”

   如果存在未完成变更,明确说明将带警告归档.

8. **对每个确认的变更执行归档**

   按确定的顺序处理(遵循冲突解决顺序):

   a. **如存在 delta 规范则同步规范**:
      - 使用 openspec-sync-specs 的方式(agent 驱动的智能合并)
      - 冲突时按已确定的顺序应用
      - 记录是否已同步

   b. **执行归档**:
      ```bash
      mkdir -p openspec/changes/archive
      mv openspec/changes/<name> openspec/changes/archive/YYYY-MM-DD-<name>
      ```

   c. **记录每个变更的结果**:
      - 成功:已成功归档
      - 失败:归档出错(记录错误)
      - 跳过:用户选择不归档(如适用)

9. **显示摘要**

   展示最终结果:

   ```
   ## 批量归档完成

   已归档 3 个变更:
   - schema-management-cli -> archive/2026-01-19-schema-management-cli/
   - project-config -> archive/2026-01-19-project-config/
   - add-oauth -> archive/2026-01-19-add-oauth/

   跳过 1 个变更:
   - add-verify-skill(用户选择不归档未完成变更)

   规范同步摘要:
   - 已同步 4 个 delta 规范到主规范
   - 已解决 1 个冲突(auth:按时间顺序应用两者)
   ```

   如果有失败:
   ```
   失败 1 个变更:
   - some-change: 归档目录已存在
   ```

**冲突解决示例**

示例 1:仅一个已实现
```
Conflict: specs/auth/spec.md touched by [add-oauth, add-jwt]

Checking add-oauth:
- Delta adds "OAuth Provider Integration" requirement
- Searching codebase... found src/auth/oauth.ts implementing OAuth flow

Checking add-jwt:
- Delta adds "JWT Token Handling" requirement
- Searching codebase... no JWT implementation found

Resolution: Only add-oauth is implemented. Will sync add-oauth specs only.
```

示例 2:两者均已实现
```
Conflict: specs/api/spec.md touched by [add-rest-api, add-graphql]

Checking add-rest-api (created 2026-01-10):
- Delta adds "REST Endpoints" requirement
- Searching codebase... found src/api/rest.ts

Checking add-graphql (created 2026-01-15):
- Delta adds "GraphQL Schema" requirement
- Searching codebase... found src/api/graphql.ts

Resolution: Both implemented. Will apply add-rest-api specs first,
then add-graphql specs (chronological order, newer takes precedence).
```

**成功输出**

```
## 批量归档完成

已归档 N 个变更:
- <change-1> -> archive/YYYY-MM-DD-<change-1>/
- <change-2> -> archive/YYYY-MM-DD-<change-2>/

规范同步摘要:
- 已同步 N 个 delta 规范到主规范
- 无冲突(或:已解决 M 个冲突)
```

**部分成功输出**

```
## 批量归档完成(部分)

已归档 N 个变更:
- <change-1> -> archive/YYYY-MM-DD-<change-1>/

跳过 M 个变更:
- <change-2>(用户选择不归档未完成变更)

失败 K 个变更:
- <change-3>: 归档目录已存在
```

**无可归档变更时输出**

```
## 没有可归档的变更

未找到活动中的变更.使用 `/opsx:new` 创建新的变更.
```

**护栏**
- 允许任意数量的变更(1+ 可用,2+ 更常见)
- 始终提示选择,不要自动选择
- 提前检测规范冲突并通过检查代码库解决
- 当两者都已实现时,按时间顺序应用规范
- 仅在实现缺失时跳过规范同步(提示警告)
- 确认前清晰展示每个变更的状态
- 整批只做一次确认
- 跟踪并报告所有结果(成功/跳过/失败)
- 移动时保留 .openspec.yaml
- 归档目录使用当前日期:YYYY-MM-DD-<name>
- 若归档目标已存在,当前变更失败但继续处理其他变更

