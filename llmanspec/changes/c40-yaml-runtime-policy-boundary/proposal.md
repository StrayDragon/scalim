---
depends_on: []
branch: sdd/c40-yaml-runtime-policy-boundary
base_sha: 8982be89879228f589d050b47c1f4ad34bdb5f71
checkpointed: false
---

# YAML 编排 vs Python runtime policy：边界收口（重开）

> **状态**：措施 I/II/III + 细项 **1A/2A/3A** 已锁（见 `design.md`）。证据：`evidence-notes.md`。  
> 下一步：`change start` → specs landing → apply。

## Why

YAML 残留随部署变化的旋钮；平铺参数难学。要：运行策略进 Python、**typed oneof**、能迁出的迁出（0.10 友好错、0.11 清债）。

## What Changes

- **I** `lookup_chunk_size`：YAML 迁出 → Python `LookupChunking` oneof  
- **II** `sources.*.cache_mode` 与 `$rows.cache_mode`：YAML 留 + Python typed 覆盖（类型拆名）  
- **III** encoding / allow_formulas / outputs.write：保留 + 钉默认（encoding 已是 `utf-8`）  
- docs/skill/AGENTS New knob gate（已部分落地）  

## Capabilities

预计：`yaml-dsl-runtime-policy-boundary` / `governance-mainline-principles`；schema/runtime/docs/skills（B.5 后 start）。

## Impact

- 0.10.*：I 对残留 YAML 友好 fail-fast；II/III 增强覆盖与测试  
- 0.11.*：I 类字段解析债批量移除  
- Breaking：写 `lookup_chunk_size` 的 YAML 需改 Python  

## Ethics

- `ethics.risk_level`: medium  
- `ethics.prohibited_actions`: 未设计 typed 面就平铺新旋钮；静默忽略 YAML；回流 budget/`write_defaults`  
- `ethics.required_evidence`: design 措施表 + evidence 片段 + 默认值核对  
- `ethics.refusal_contract`: B.5 未答完不改 schema  

## Open Questions

无（细项已锁 1A/2A/3A）。实现期签名命名可微调，不得改措施 I/II/III 与挂载抉择。