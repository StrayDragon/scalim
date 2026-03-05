---
name: openspec-sync-specs
description: Sync delta specs from a change to main specs. Use when the user wants to update main specs with changes from a delta spec, without archiving the change.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.1.1"
---

将变更中的 delta 规范同步到主规范.

这是一个 **agent 驱动** 的操作——你将读取 delta 规范并直接编辑主规范以应用变更.这允许智能合并(例如只添加一个场景,而不是复制整个需求).

**输入**:可选指定变更名称.如果省略,先判断是否可从对话上下文推断;若含糊或不明确,必须提示可用的变更.

**步骤**

1. **如果未提供变更名称,提示进行选择**

   运行 `openspec list --json` 获取可用变更.使用 **AskUserQuestion 工具** 让用户选择.

   显示有 delta 规范的变更(`specs/` 目录下).

   **重要**:不要猜测或自动选择变更.始终让用户选择.

2. **查找 delta 规范**

   在 `openspec/changes/<name>/specs/*/spec.md` 中查找 delta 规范文件.

   每个 delta 规范文件包含类似以下章节:
   - `## ADDED Requirements` - 要新增的需求
   - `## MODIFIED Requirements` - 对现有需求的修改
   - `## REMOVED Requirements` - 要移除的需求
   - `## RENAMED Requirements` - 要重命名的需求(FROM:/TO: 格式)

   如果未找到 delta 规范,告知用户并停止.

3. **对每个 delta 规范,将变更应用到主规范**

   对于 `openspec/changes/<name>/specs/<capability>/spec.md` 中的每个能力:

   a. **阅读 delta 规范**,理解预期变更

   b. **阅读主规范**:`openspec/specs/<capability>/spec.md`(可能尚不存在)

   c. **智能应用变更**:

      **ADDED Requirements:**
      - 如果主规范不存在该需求 → 添加
      - 如果已存在 → 更新以匹配(视为隐式 MODIFIED)

      **MODIFIED Requirements:**
      - 在主规范中找到该需求
      - 应用变更,包括:
        - 新增场景(不需要复制已有场景)
        - 修改已有场景
        - 修改需求描述
      - 保留 delta 中未提及的场景/内容

      **REMOVED Requirements:**
      - 从主规范中移除整个需求块

      **RENAMED Requirements:**
      - 找到 FROM 需求,并重命名为 TO

   d. **若能力尚不存在主规范**:
      - 创建 `openspec/specs/<capability>/spec.md`
      - 添加 Purpose 章节(可简短,标记为 TBD)
      - 添加包含 ADDED Requirements 的 Requirements 章节

4. **展示摘要**

   应用所有变更后,总结:
   - 更新了哪些能力
   - 做了哪些变更(新增/修改/移除/重命名需求)

**Delta 规范格式参考**

```markdown
## ADDED Requirements

### Requirement: New Feature
The system SHALL do something new.

#### Scenario: Basic case
- **WHEN** user does X
- **THEN** system does Y

## MODIFIED Requirements

### Requirement: Existing Feature
#### Scenario: New scenario to add
- **WHEN** user does A
- **THEN** system does B

## REMOVED Requirements

### Requirement: Deprecated Feature

## RENAMED Requirements

- FROM: `### Requirement: Old Name`
- TO: `### Requirement: New Name`
```

**关键原则:智能合并**

不同于程序化合并,你可以应用 **部分更新**:
- 要新增一个场景,只需在 MODIFIED 中包含该场景——无需复制已有场景
- delta 表达的是 *意图*,不是整体替换
- 使用判断力进行合理合并

**成功输出**

```
## 规范已同步:<change-name>

已更新主规范:

**<capability-1>**:
- 新增需求:"New Feature"
- 修改需求:"Existing Feature"(新增 1 个场景)

**<capability-2>**:
- 创建新的规范文件
- 新增需求:"Another Feature"

主规范已更新.该变更仍保持激活状态——在实施完成后归档.
```

**护栏**
- 修改前先阅读 delta 和主规范
- 保留 delta 未提及的既有内容
- 如有不清楚,先询问
- 变更过程中展示你在修改什么
- 操作应具备幂等性——运行两次结果一致

