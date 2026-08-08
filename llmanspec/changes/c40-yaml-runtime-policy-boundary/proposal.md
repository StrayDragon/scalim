---
depends_on: []
---

# Draft change: YAML 编排 vs Python runtime policy 边界收紧

> **状态**：调研已完成 R1–R3（见 `inventory.md` / `design.md`）。**尚未** `change start`；**不**改 schema。  
> **结论**：**暂不迁**残留策略争议键；大头已在既有 change 迁出。可选 follow-up 仅文档对齐（见 design R3）。

## Why

仓库硬规则：YAML = 编排 + 资源身份；Python = 写策略 / runtime policy。c30 dig 触发「YAML 里是否还该留调优键」的疑问。

## What（已交付调研）

- **R1** `inventory.md`：键分类 + 迁移成本 + 建议  
- **R2** `design.md`：MUST/SHOULD / 禁止项  
- **R3**：0 个迁键 change；可选文档对齐 `c41-...`；明确不做迁出 `lookup_chunk_size`

## Capabilities

本阶段不进 live specs。若日后要合约化，再 `llman-sdd-propose` 新 change。

## Impact

- 调研期：零代码、零 schema。  
- 后续：默认不 breaking；有产品需求再扩展 Python 缓存，而非删 YAML 粗枚举。

## Ethics

- `ethics.risk_level`: low（调研收口）  
- `ethics.prohibited_actions`: 未盘点删键；误迁编排键；复活 budget/`write_defaults`  
- `ethics.required_evidence`: inventory + R2 + R3（已齐）  
- `ethics.refusal_contract`: 无库存清单不得删键（已满足）

## Open Questions（关闭）

1. `cache_mode` / `params` → inventory 已归类；params 留 YAML；cache_mode 暂留。  
2. workflow vs demand → 同一套原则；workflow 运行期已 Python-only。  
3. 第一刀 → **文档收口，不 breaking**。
