# Workflow 迭代方向 HANDOFF（临时）

> **临时进度追踪**：`c20` + `c30` 均已归档。本文件可删除，或迁入 `docs/doc/dev/` 常驻页。  
> 会话 SSOT 日期：2026-07-12。

## 方向一句话

- **YAML DSL**：只承担编排与资源 identity（runs / 依赖 / `resources.*.id+variant+path` / `outputs.to` / 内容字段）。
- **Python**：承担 book 写入策略、`budget` 及同类调参（`ResourcesPolicy`；开箱 builtin defaults；显式 policy 覆盖）。
- **共享 book**：多节点写入仍合法；openpyxl 仅最终 commit；峰值来自 plan 全量物化；写后可尽早释放 demand artifact，plan segments 在 commit/discard 后释放。

## Archived（本方向）

| Change | 归档路径 |
| --- | --- |
| `c20-book-write-policy-python-ssot` | `llmanspec/changes/archive/2026-07-12-c20-book-write-policy-python-ssot/` |
| `c30-workflow-shared-book-memory` | `llmanspec/changes/archive/2026-07-12-c30-workflow-shared-book-memory/` |

## 已拍板决策

| # | 决策 |
| --- | --- |
| 1 | `resources.books/files` 的 **id / variant / path**（及 `export_xlsx.path`）**留 YAML** |
| 2 | **`write_defaults` → Python SSOT** |
| 3 | **`budget` → Python SSOT**（可选；omit = unlimited；仅 `xlsx_memory` 强制） |
| 4 | **`allow_formulas` / `encoding` 暂保持 YAML 可写** |
| 5 | 开箱：不传 policy = builtin defaults；budget unlimited |
| 6 | c30 P0：write-consumer 尽早 discard demand artifact；commit/discard 后清 plan segments |
| 7 | budget 产品态度：先保留可选 fail-fast；后续调研用量；倾向限速/背压（见 futures） |

## 后续（futures / notplan）

- spill / seal / `xlsx_file` budget / 边写 openpyxl / budget 限流或移除：`llmanspec/futures/xlsx-file-numeric-type-loss/future.md`
- streaming notplan reframe：`llmanspec/notplan/c1-streaming-xlsx-output/`、`c1-runtime-performance-profiles/`

## 不要做的事

- 不要把 flush/streaming/budget/write_defaults 重新加回 YAML 主线
- 不要默认「边写边 openpyxl」破坏原子 discard（除非独立 change + 显式 profile）
- 不要手改 `*.gen.json` schema

## 指针

- Archived c20: `llmanspec/changes/archive/2026-07-12-c20-book-write-policy-python-ssot/`
- Archived c30: `llmanspec/changes/archive/2026-07-12-c30-workflow-shared-book-memory/`
- Skill upgrade: `agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-07-12-book-write-policy-python-ssot.md`
- Review checklist: `docs/doc/yaml-dsl/review-checklist.md`
