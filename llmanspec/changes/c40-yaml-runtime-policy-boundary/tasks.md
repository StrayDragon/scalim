# Tasks: c40-yaml-runtime-policy-boundary

> **调研草稿**；未 `change start`。R1–R3 已完成；术语/缺口已补强。文档对齐 → **quick**（见 `design.md` R3），不另开 change。

## R1 盘点

- [x] R1.1 从 capability-matrix + schema 列出 YAML 键清单
- [x] R1.2 标注 编排/身份 | 策略/调优 | 内容/映射
- [x] R1.3 标注是否已有 Python options 覆盖；迁移成本低/中/高
- [x] R1.4 写入 `inventory.md`
- [x] R1.5 补强：统一术语表；`validate_unique_field_names`；`allow_formulas`/`encoding`；两套 `cache_mode`；schema source 键对拍

## R2 原则

- [x] R2.1 起草 MUST/SHOULD（`design.md`）
- [x] R2.2 对照 AGENTS / book write policy / c30 / 0.10 例外
- [x] R2.3 明确「禁止未盘点删键」与混称禁令

## R3 follow-up

- [x] R3.1 结论：**暂不迁**；不做迁出 `lookup_chunk_size`
- [x] R3.2 文档对齐改走 **quick**；弃用独立 docs change（不进仓库）
- [x] R3.3 （quick）按 `design.md` R3 Q1–Q6 改入口文档/skill

## 门禁

- [x] 本调研阶段不改 live `llmanspec/specs/**`
- [x] `just llmanspec-sanitize` 可扫过本目录
