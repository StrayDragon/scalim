# Tasks: c40-yaml-runtime-policy-boundary

> **调研草稿**；未 `change start`。R1–R3 已完成。

## R1 盘点

- [x] R1.1 从 capability-matrix + schema 列出 YAML 键清单
- [x] R1.2 标注 编排/身份 | 策略/调优 | 内容/映射
- [x] R1.3 标注是否已有 Python options 覆盖；迁移成本低/中/高
- [x] R1.4 写入 `inventory.md`

## R2 原则

- [x] R2.1 起草 MUST/SHOULD（`design.md`）
- [x] R2.2 对照 AGENTS / book write policy / c30 例外
- [x] R2.3 明确「禁止未盘点删键」

## R3 延后提案

- [x] R3.1 结论：**暂不迁**；可选文档 follow-up `c41-yaml-policy-boundary-docs`；不做迁出 `lookup_chunk_size`
- [ ] R3.2 （可选）若要文档进 live：另开 propose；本目录可保留为调研 SSOT 或 archive

## 门禁

- [x] 本调研阶段不改 live `llmanspec/specs/**`
- [x] `just llmanspec-sanitize` 可扫过本目录
