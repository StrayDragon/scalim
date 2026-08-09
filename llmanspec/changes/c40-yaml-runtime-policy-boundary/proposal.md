---
depends_on: []
---

# Draft change: YAML 编排 vs Python runtime policy 边界收紧

> **状态**：调研 R1–R3 已完成并补强术语/缺口键（见 `inventory.md` / `design.md`）。**尚未** `change start`；**不**改 schema。  
> **结论**：**暂不迁**灰区键；大头已在既有 change 迁出。文档对齐走 **`llman-sdd-quick`**（不另开 docs change）。

## Why

仓库硬规则：YAML = 编排 + 资源身份；Python = 写策略 / runtime policy。c30 dig 触发「YAML 里是否还该留调优键」的疑问。0.10.* 需要**同一套可维护心智模型**，避免 inventory / checklist / skill / release 各说各话。

## What（已交付调研）

- **R1** `inventory.md`：键分类 + 统一术语 + 迁移成本 + 建议；补 `validate_unique_field_names`、`allow_formulas`/`encoding`；钉死两套 `cache_mode`
- **R2** `design.md`：MUST/SHOULD / 灰区 / 禁止项（对齐 0.10 无 YAML breaking）
- **R3**：0 个迁键 change；文档对齐清单见 `design.md` R3（quick path）；明确不做迁出 `lookup_chunk_size`

## Capabilities

本阶段不进 live specs。合约仍以既有 `yaml-dsl-runtime-policy-boundary` / `governance-mainline-principles` 为准。文档叙事由 quick 改入口页收口（无独立 docs change）。

## Impact

- 调研期：零代码、零 schema。  
- 后续文档对齐：默认不 breaking；有产品需求再扩展 Python 缓存，而非删 YAML 粗枚举。

## Ethics

- `ethics.risk_level`: low（调研收口）  
- `ethics.prohibited_actions`: 未盘点删键；误迁编排键；复活 budget/`write_defaults`；混称两套 cache_mode  
- `ethics.required_evidence`: inventory + R2 + R3（已齐）  
- `ethics.refusal_contract`: 无库存清单不得删键（已满足）

## Open Questions（关闭）

1. `cache_mode` / `params` → inventory 已归类；params/`$rows.cache_mode` 留 YAML；`sources.*.cache_mode` 暂留灰区。  
2. workflow vs demand → 同一套原则；workflow 运行期已 Python-only。  
3. 第一刀 → **文档收口（quick），不 breaking**。
