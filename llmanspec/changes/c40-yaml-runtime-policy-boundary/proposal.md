---
depends_on: []
---

# YAML 编排 vs Python runtime policy：边界收口（重开）

> **状态**：调研重开。早期「灰区暂不迁」**作废**。目标：一步到位把 **运行可变 knobs 收口 Python**，YAML 保留可移植编排/内容；以全量 inventory 为 SSOT，**本文不写死某键去留**。  
> 未 `change start`；未改 schema。

## Why

主线原则是 `YAML = authoring`、`Python = runtime policy`，但 YAML 仍残留可能随部署/入口变化的配置（典型候选：分片大小、粗缓存模式等）。把它们写死在 YAML 会降低可移植性，并迫使「同 demand、不同环境」靠改文件。需要全量清点后，一次性收口到可维护、理解统一的边界。

## What Changes（当前阶段：规划与盘点）

- 重写 `inventory.md`：schema 全量清点 + 开放轴（A/C/R/M/X/?），不作终局建议列  
- 重写 `design.md`：目标态 = 动态/环境 knobs → Python；一步到位交付面  
- 废止「暂不迁」叙事；docs/skill 入口改为指向开放盘点，避免定论话术  
- **尚未**：schema 迁出、Python API 扩展、live specs 条款（待 inventory 闭合 + start）

## Capabilities

落地时可能触及（待定，不在此锁）：

- `yaml-dsl-runtime-policy-boundary` / `governance-mainline-principles`  
- 相关 schema / runtime options / docs / skills  

## Impact

- 调研重开：以文档与盘点为主  
- 落地后：对定为 R 的 YAML 键可能 breaking（需兼容窗/升级卡）；具体范围以闭合后的迁移切片为准  

## Ethics

- `ethics.risk_level`: medium（方向重开；落地或 breaking）  
- `ethics.prohibited_actions`: 未盘点删键；在 inventory 写死终局去留；回流 budget/`write_defaults`；静默忽略 YAML  
- `ethics.required_evidence`: 全量 path 索引；每条 R 候选的「为何动态」笔记；Python 覆盖草图  
- `ethics.refusal_contract`: 无闭合 inventory 不得改 schema  

## Open Questions

见 `inventory.md` §8；由 tasks 推进闭合，不在 proposal 填答案。
