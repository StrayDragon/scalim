## Context

本变更聚焦 `scalim.events` 与 `scalim.sinks` 两个包根模块的“公共导出面”（`__all__` + re-export）。

现状（截至 2026-03-28）：

- `scalim.events.__all__=74`：包含大量 typed payload 数据类与常量；其中绝大多数仅被仓内 tests 引用，用户可见 notebooks 实际只需要少量事件类型常量。
- `scalim.sinks.__all__=33`：除接口与常用 sinks 外，还聚合了不少内部实现 helper / 中间态工具；这些符号的存在主要是内部实现与测试便捷，并非稳定用户契约的必要组成。

约束：

- `src/scalim/` 必须保持 Python 3.6 兼容。
- 不提供兼容层/alias/shim：破坏性迁移一次性完成并同步仓内所有引用点。
- 文档治理：不手改 `.gen.*` 文件与 `BEGIN/END AUTOGEN` 注入区块内部；以 `just gen-docs`/`just qa` 漂移门禁为准。

## Goals / Non-Goals

**Goals:**

- 以用户视角收敛 `scalim.events` / `scalim.sinks` 的公共导出面：只保留真实用户需要的稳定契约。
- 将内部测试/实现便捷依赖迁移到内部模块导入路径（允许破坏性迁移）。
- 将 events/sinks 纳入 public API 治理闭环：
  - 显式 `__all__` 白名单（可审计、可回归）
  - 用户可见材料不得推广内部实现模块路径
  - `just qa` 作为验收门禁

**Non-Goals:**

- 不引入新的顶层公共 facade（遵循 `module-organization`）。
- 不改变事件/输出的运行时语义（仅调整公共导出与推荐导入）。
- 不在本变更中为 typed payload 提供新的对外类型层（如需，作为后续独立提案）。

## Decisions

### 1) 用户视角的“需要导出”口径

**Decision**：以用户可见 notebooks/examples 与 docs 中出现的导入需求为基线，定义“稳定导出集”；tests/packages 的便捷导入不再作为导出依据。

**Alternatives considered:**
- 以 tests 的导入需求为准：会把内部便利长期锁成公共契约，治理成本不可控（拒绝）。

### 2) `scalim.events` 的公共契约收敛

**Decision**：

- `scalim.events` 包根仅作为“事件公共契约入口”，公共导出收敛为：
  - `Event` envelope 与辅助函数（如时间戳/运行标识）
  - 事件类型常量（`EVENT_*`）与目录查询（`EventDescriptor` + `get_event_catalog*`）
  - workflow attribution/prefix 等用于跨 demand/workflow 归因的稳定 key/前缀
- typed payload 数据类（`BatchStartEvent` 等）不再作为公共导入契约；内部实现与 tests 可直接从内部模块导入。

**Rationale**：typed payload re-export 是 `events.__all__` 扩大的主要来源；用户侧更稳定的依赖应是 `event_type` 与 payload 的字段/键语义，而不是内部数据类名与导入路径。

**Alternatives considered:**
- 保留全量 typed payload 数据类作为公共契约：稳定性成本过高，且与“用户视角最小导出”冲突（拒绝）。
- 单独提供 `scalim.events.payloads` 等稳定模块：可行，但属于新增对外能力与维护面，暂不纳入本变更（保留为后续选项）。

### 3) `scalim.sinks` 的公共契约收敛

**Decision**：

- `scalim.sinks` 包根仅导出：
  - sink 接口/基类（contracts）
  - 常用 sinks（内存 sink、CSV/Excel 等）
- 移除仅用于内部实现/测试的 helper 与中间态工具在包根的聚合导出；需要时由内部实现与 tests 直接从内部模块导入。

**Rationale**：用户侧需要的是“可实现/可替换的 sink 契约 + 可直接用的少量 sinks”；内部 helper 作为公共 API 的长期维护价值低且会扩大破坏性半径。

**Alternatives considered:**
- 将 sinks 全部拆成多个稳定子模块并让包根几乎为空：更彻底但迁移成本更高，且会影响既有用户心智；本变更优先做“包根收敛”，必要的分组在后续再做（暂不做）。

### 4) 治理与回归门禁

**Decision**：

- 将 `scalim.events` 与 `scalim.sinks` 纳入 curated public surface gate（显式模块白名单 + 精确 `__all__` 断言）。
- 扩展用户可见材料扫描规则：禁止在 docs/notebooks/skills 中出现 events/sinks 的内部实现模块路径（避免把内部路径当作官方用法推广）。

## Risks / Trade-offs

- [Downstream break] 外部调用方可能依赖现有 re-export 的 payload/工具 → 通过明确 BREAKING 变更、迁移说明与最小稳定集合缓解；如存在下游清单，可在不泄露路径的前提下做行号级扫描评估。
- [类型体验下降] 不再公开 typed payload 数据类会降低类型提示 → 通过 `EventDescriptor.key_fields` 与文档描述字段语义缓解；如确有需求，再单独引入稳定 payload 类型层。
- [迁移工作量] tests 中存在大量 `from scalim.events import <payload>` 的引用 → 采用机械迁移（导入改为内部模块）+ `just qa` 回归。

## Migration Plan

1. 固化新的稳定导出集（`scalim.events` / `scalim.sinks` 的 `__all__` 目标清单）。
2. 实施包根收敛（调整 re-export + `__all__`），并同步迁移仓内引用点（tests/packages/notebooks）。
3. 更新 curated public surface gate 与用户可见材料扫描规则，确保后续不回归扩大导出面/推广内部路径。
4. 跑 `just qa` + `just openspec-check` 验收。

## Open Questions

- 是否需要提供一个独立的、明确标注为“高级/可变”的 typed payload 模块（例如 `scalim.events.payloads`），以便强类型使用方可 opt-in？

