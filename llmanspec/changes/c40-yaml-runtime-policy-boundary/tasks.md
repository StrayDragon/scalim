# Tasks: c40-yaml-runtime-policy-boundary

> **调研草稿**；给后续 agent。未 `change start`。

## R1 盘点

- [ ] R1.1 从 capability-matrix + schema 列出 YAML 键清单
- [ ] R1.2 标注 编排/身份 | 策略/调优 | 内容/映射
- [ ] R1.3 标注是否已有 Python options 覆盖；迁移成本低/中/高
- [ ] R1.4 写入 `inventory.md`（本目录）或 design 附表

## R2 原则

- [ ] R2.1 起草 MUST/SHOULD（仅本 change 文档）
- [ ] R2.2 对照 AGENTS / book write policy / c30 例外，消除冲突
- [ ] R2.3 明确「禁止未盘点删键」

## R3 延后提案

- [ ] R3.1 给出 0～3 个 follow-up change 标题+范围，或「暂不迁」
- [ ] R3.2 若升格：`llman-sdd-propose` 新建正式 change；本目录改为指针或 archive

## 门禁

- [ ] 本调研阶段不改 live `llmanspec/specs/**`（无 Branch binding）
- [ ] `just llmanspec-sanitize` 可扫过本目录
