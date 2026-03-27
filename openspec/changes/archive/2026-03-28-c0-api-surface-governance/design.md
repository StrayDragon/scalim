## Context

本仓库对公共 API 的基本立场是“可导入 ≠ 可承诺”：稳定入口由显式白名单与 `__all__` 管控，而内部实现路径即使当前可导入也应视为非契约（见 `openspec/specs/public-api-surface-governance/spec.md` 与 `openspec/specs/module-organization/spec.md`）。同时还存在若干硬约束：

- `src/scalim/` 运行时保持 Python 3.6 兼容；包内优先相对导入。
- 顶层 `scalim` 不做公共 re-export 聚合，避免引入可选依赖导入副作用（`pandas`/`openpyxl`/`rich`/`jsonschema` 等）。
- 避免 stdlib 同名冲突模块文件（例如 `types.py`），仓库有脚本门禁（`scripts/check-stdlib-module-collisions.py`）。
- `if TYPE_CHECKING:` 仅用于 type-only imports/aliases，不得用于“伪接口”。

现状问题来自两个维度：

1) **模块导出面不一致**：`src/scalim/` 存在较多模块缺少 `__all__`，且少数模块的 `__all__` 误包含 `_...` 内部符号，导致“对外可见面”难以审计与稳定治理。

2) **仓内引用固化内部路径**：tests/packages/notebooks 对某些叶子模块/内部路径有高频直接引用（例如 `scalim.spec.ir.sources` 等），这会显著放大后续重构的迁移成本与风险，并可能把内部路径沉淀为事实公共 API。

基线审计数据（`2026-03-27`，详见 `references/api-surface-audit-report.md`）：
- `src/scalim/` Python files：275
- 定义 `__all__`：160；缺失 `__all__`：115
- `__init__.py`：54
- `__all__` 中包含 `_...`（非 dunder）泄漏：5 个模块（workflow/resources_* + by_yaml/runtime/conversion）
- 缺失 `__all__` 集中区：`dsl/by_yaml/config_parsing`、`dsl/by_yaml/schema_dsl`、`execution/executor`、`ob`、`spec/ir`、`hooks`、`cli`

本 change 将 `_NEXT/` 与 `.tmp/api-surface-audit-report.md` 的内容收敛为 OpenSpec 工件与 references，形成唯一 SSOT。

## Goals / Non-Goals

**Goals:**
- 建立可复核的“API 表面治理”决策与实施路线图：现状审计、关键冲突点、阶段化任务与验收口径。
- 强化 public surface governance：补齐 `__all__` 封堵策略、禁止 `_...` 误导出、并提供可自动化回归的门禁点。
- 允许在不提供兼容层的前提下，对**非稳定入口**的内部实现路径进行一次性重构/封装（breaking allowed），并同步迁移仓内所有调用点。

**Non-Goals:**
- 本工件不直接落地大规模代码重构（仅整理 SSOT 与阶段任务）；实现应在后续按 tasks 分批推进。
- 不扩大默认稳定公开入口目录；新增/扩大稳定入口需要显式提案与对应回归覆盖（examples gate / curated surface gate）。

## Decisions

### 1) SSOT 与文件治理边界

- SSOT：`openspec/changes/c0-api-surface-governance/`（proposal/design/specs/tasks + references）。
- 清理：删除 `_NEXT/` 与 `.tmp/api-surface-audit-report.md`；审计报告与原始 prompt/plan 迁移到本 change 的 `references/`。
- docs-site：若后续需要把结论同步到 docs-site，遵循生成物/注入区块规则，入口为 `just gen-docs`（不手改 `.gen.` 与 AUTOGEN 区块内部）。

### 2) 稳定入口与“内部路径”边界

- 稳定入口维持当前顶层文档与规范口径（`scalim.dsl.by_yaml`、`scalim.spec.ir`、`scalim.planning`、`scalim.execution`、`scalim.ob` + curated workflow loaders 等）。
- 非白名单路径即使当前可导入，也视为内部实现细节；允许进行 breaking 的结构调整与命名收敛，并一次性迁移仓内引用，不保留兼容别名。

### 3) `__all__` 治理策略

- 稳定入口模块：必须使用显式 `__all__` 白名单，并保持与示例/回归 gate 的覆盖一致。
- 内部实现模块：优先通过 `__all__ = []` 明确“非公共导出面”，避免 `from ... import *` 意外扩大导出。
- 禁止任何模块的 `__all__` 包含非 dunder 的 `_...` 名称；该类条目应视为内部符号泄漏。

### 4) Barrel / re-export 策略

- 遵循 `__init__.py` 最小化原则：避免在内部实现子包通过 `__init__.py` re-export 暴露实现符号。
- 对是否为 `events/`、`hooks/`、`sinks/` 等包建立 package-root 的稳定入口保持审慎：只有在明确将其纳入稳定入口目录、并能保证可选依赖不在 import-time 触发失败时才考虑；否则继续要求调用方从定义模块显式导入。

### 5) types 聚合入口的命名与实现形态

- 不引入 `src/scalim/types.py` 这类 stdlib 同名冲突模块文件。
- 若需要 `scalim.types` 作为用户侧类型聚合入口，优先使用 package 形态 `src/scalim/types/__init__.py`（避免被 stdlib collision 脚本识别为冲突文件），并保持 `typedefs.py` 为内部 SSOT；是否推进取决于回归覆盖与迁移收益评估。

## Risks / Trade-offs

- [迁移爆炸半径] 内部路径重命名/移动会影响 tests/packages/notebooks 大量导入点 → 采用分批（≤10 文件）与每批 `just qa` 的策略，并优先迁移高频热点路径。
- [可选依赖副作用] 若将 sinks 提升为稳定入口，需避免 `openpyxl`/`pandas` 等可选依赖在 import-time 引发失败 → 需要 lazy/segmented export 策略与专门回归。
- [治理过度] 强行要求所有模块补齐 `__all__` 可能带来维护成本 → 以“稳定入口非空白名单 + 内部实现空白名单 + 禁止 `_...` 泄漏”为先，逐步扩大覆盖范围。

## Migration Plan

1. Phase 0（已完成）：生成并存档 API surface 审计报告（迁移到本 change 的 references）。
2. Phase 1：修复 `__all__` 中 `_...` 泄漏；为内部实现模块补齐 `__all__ = []`（按批次推进，每批后 `just qa`）。
3. Phase 2：收敛“官方可依赖入口”的目录与导入推荐；必要时调整 curated gate 与 examples gate。
4. Phase 3：对内部实现路径做结构封装（`_internal/` / `_` 前缀等）并一次性迁移仓内引用；不保留 shim。
5. Phase 4：评估并落地 `scalim.types`（package 形态）或保持 `scalim.typedefs` 作为官方类型入口。

## Open Questions

- `sinks` 是否应成为稳定入口的一部分？若是，如何在不引入可选依赖 import-time 失败的前提下提供可审计 `__all__`？
- `events`/`hooks` 是否需要 package-root 入口，还是继续要求从定义模块导入并由 docs/examples 通过现有稳定入口展示扩展点？
- `scalim.types` 的收益是否足以覆盖迁移成本？是否需要同步调整 curated surface 与示例覆盖？
