## Context

当前仓库 `tests/` 以“平铺文件 + 文件名前缀”组织，规模已进入“需要治理”的阶段：

- 用例与文件数量较大，且 YAML/Workflow 相关用例占比最高，少数文件体量巨大（既承担契约回归，也承担分支覆盖驱动的 guard/coverage）。
- 默认 pytest 入口由 `pyproject.toml` 的 `[tool.pytest.ini_options] addopts` 提供：非 bench 默认执行 + `--cov-fail-under=100` 的 100% 覆盖率门禁（覆盖范围为 `src/scalim/**`，排除 vendor/cli 等边缘目录）。
- `bench` 已通过 marker 与独立入口隔离（`tests/bench/` + `-m bench`）。
- YAML DSL / workflow 的测试夹具大量依赖 **字符串引用**（例如 `loader: "tests.conftest.mock_loader"` / `call_by: "tests.call_by_fns:..."`）与 `allowed_modules` 白名单；这意味着“移动/改名测试模块”会直接破坏运行期解析与 allowlist。

同时，上游 `main` 可能持续变动，不能假设本 change 从提案到落地期间仓库形态不变；因此实施必须以“先调研再搬迁、按 domain 小批量推进”为基本节奏，以降低过期风险与冲突面。

## Goals / Non-Goals

**Goals:**
- 将 `tests/` 重组为**领域（domain）**套件目录，使贡献者以“用户视角/核心链路能力”进入测试，而不是以内部实现路径进入测试。
- 在不降低 `src/scalim` **100% 覆盖率门禁**的前提下，降低重复脚手架与重叠断言（尤其是 `*_additional.py` 与 coverage-only 风格用例的扩散）。
- 对 public API（以扫描 `src/scalim/**` 中 `__all__` 导出自动生成的 catalog 为准）建立更完整的 pytest 套件覆盖，并与 `notebooks/marimo/example_public_api_suite/` 的示例覆盖对齐；两条链路都覆盖，但避免“同一套重逻辑跑两遍”的低效重叠。
- 将“可被 YAML 字符串引用的测试夹具模块”收敛到稳定边界（`tests/fixtures/`），并建立可审计/可扫描的治理规则，避免未来搬迁再次引入隐性破坏点。

**Non-Goals:**
- 不改变 `src/scalim` 的运行期行为与对外 API（本 change 仅重组与优化测试套件 + 示例覆盖对齐）。
- 不以“严格映射 `src/scalim/**` 包路径”作为测试目录结构目标（内部实现会频繁重构，强绑定会增加维护熵）。
- 不保留旧测试路径的兼容 shim/stub；迁移采取一次性升级（移动/改名即全仓同步更新引用点）。

## Decisions

### Decision 1: tests 以 domain 套件组织，而非按实现包路径映射

**Decision**: 引入 `tests/<domain>/...` 的领域套件目录（例如 `public_api/`、`yaml_dsl/`、`workflow/`、`execution/`、`planning/`、`sinks/`、`ob/`、`governance/`、`integration/`），并将现有 `tests/bench/` 保持不变。

**Rationale**: domain 是相对稳定的概念边界；实现包路径会随重构频繁漂移。domain 组织能提升定位速度与评审可读性，同时降低“因重构引发的大规模测试路径漂移”。

**Alternatives considered**:
- 按 `src/scalim/**` 包树映射：与当前“内部重构频繁”的现实冲突，长期维护成本更高。
- 继续平铺文件：短期无迁移成本，但重复与定位问题继续恶化。

### Decision 2: 字符串引用（allowlist）夹具模块必须收敛到稳定边界

**Decision**: 对“可被 YAML/Workflow 字符串引用”的测试夹具采取一次性重构升级策略：

- **所有**会被 YAML `loader:`/`call_by:` 字符串引用的 callable/module MUST 一次性迁移到 `tests/fixtures/`（或其子模块）中。
- `tests/support/` 仅承载测试内部复用工具（不得被字符串引用；可自由移动/重构）。
- 迁移时 MUST 在同一批次内全仓一次性升级所有引用与 allowlist（不做兼容层/不保留旧路径 shim）。

**Rationale**: 字符串引用是“运行期契约”，必须像 public API 一样治理。将其集中可显著降低“移动文件导致 YAML 解析失败”的隐性风险。

**Alternatives considered**:
- 允许任意测试模块被引用：短期方便，但会将组织重构变成高风险操作，且难以审计。
- 为旧路径保留兼容 shim：违背“一次性升级、不做兼容”的治理原则，并会持续制造熵。

### Decision 3: public API 覆盖在 pytest 与 marimo 两条链路中同时存在，但职责不同

**Decision**:
- `notebooks/marimo/example_public_api_suite/` 继续承担“可交互示例 + 教学叙事 + 扩展点演示”的覆盖，且通过 `just examples` 作为主要 gate 执行。
- 覆盖范围 SSOT 由 public API catalog 提供：扫描 `src/scalim/**` 中所有声明了 `__all__` 的模块与导出符号（排除 `cli/`、`vendor/` 等个别目录/模块）生成并管理。
- `tests/public_api/` 收敛为“用户侧最小闭环 + 契约回归”的 pytest 套件：对 catalog 中的模块/符号做导入与 `__all__` 解析回归,并覆盖最小运行路径（`compile/run/run_workflow`、`PlanBuilder`、`ScalimEngine`、`Observability`、`events/sinks` 的基本使用）。
- 引入“对齐规则”：pytest public_api 套件与 marimo public API suite 必须覆盖同一份 catalog；pytest 不应直接复用运行 marimo 章节作为唯一方式，以避免 `just qa` 里出现“大块重复执行”。
- public API 导入指南文档改为由 catalog 自动生成的 `*.gen.md` 并纳入 drift-check（作为用户侧可读投影）。

**Rationale**: 用户要求“两边都覆盖”，但同时希望降低无效重叠。将两条链路的覆盖职责区分为“契约回归 vs 教学示例”，可以同时满足覆盖完整性与执行成本。

**Alternatives considered**:
- pytest 直接运行全部 marimo 章节作为 public API 覆盖：实现简单，但会导致 `just qa` 中 `test` 与 `examples` 在同一主题上大量重复。

### Decision 4: 覆盖率驱动用例不删除，但显式归类并去重

**Decision**:
- 将“分支覆盖驱动”的用例（`*_coverage.py`、`cover_branches`、内部 guard 覆盖等）显式归入对应 domain 的 coverage 子域或集中目录，并优先通过参数化/共享断言减少重复脚手架。
- 合并/消除 `*_additional.py` 的主题分散：同一能力应有单一 SSOT 的测试文件/套件入口，避免重复断言与重复 fixture 构造。

**Rationale**: 100% coverage 门禁要求这些边界分支必须被覆盖；治理重点是“结构与重复”，而不是牺牲覆盖率换速度。

## Risks / Trade-offs

- **[大规模移动导致 merge 冲突]** → 按 domain 分批迁移；每批在 `just test`/`just qa` 下保持全绿后再继续下一批；避免一次性大爆炸重命名。
- **[字符串引用路径破坏 YAML/Workflow 解析]** → 先 inventory 所有 `tests.*` 字符串引用与 `allowed_modules` 白名单；对被引用入口实施“保持路径”或“一次性全仓升级”策略；并引入扫描门禁防止新增散点引用。
- **[去重导致覆盖率回落]** → 每次合并/删除用例必须以覆盖率报告为准，优先用参数化替换重复而非直接删除；保持 `src/scalim` 覆盖率为 100%。
- **[pytest public_api 与 examples 双覆盖引入执行开销]** → pytest public_api 覆盖保持“最小闭环”，避免直接运行 marimo 章节；examples 保持叙事与对拍，二者互补而非重复。
- **[目录结构与命名仍可能漂移]** → 用 domain 与稳定边界治理替代“按实现包路径”的结构约束；允许内部文件更名/拆分，但要求测试组织与引用边界稳定。

## Migration Plan

1) **Inventory（先调研）**
- 统计 `tests/` 用例与文件分布（按前缀、按领域关键词、按 marker：`bench`/`slow`）。
- 全仓扫描 YAML/字符串引用：`loader:`/`call_by:`/`allowed_modules` 中的 `tests.*` 引用清单，形成“可移动/不可移动”入口表。
- 标记重复热点：`*_additional.py`、`*_coverage.py`、超大文件（行数阈值）与重复 helper（如 `_write_*` 系列）。

2) **建立骨架与边界**
- 创建 `tests/<domain>/` 目录骨架与 `tests/support/`、`tests/fixtures/` 边界。
- 先迁移 `governance/` 与纯导入/结构类测试（对字符串引用影响最小）。
- 收敛/搬迁通用 helper 到 `tests/support/`（不改变对外字符串引用）。

3) **按 domain 小批量迁移与去重**
- 每个 domain 迁移遵循：先移动（不改语义）→ 再合并/参数化去重（保持覆盖率）→ 再清理旧文件。
- 对必须调整字符串引用路径的迁移，采用“一次性全仓升级”并同步更新 allowlist；禁止残留旧路径引用。

4) **public API 对齐**
- 在 `tests/public_api/` 形成覆盖 public API catalog 的最小闭环回归（不依赖运行全部 marimo 章节）。
- 补齐 `example_public_api_suite` 缺失的 catalog 用户场景（若存在），并确保 `just examples` 覆盖完整。
- 更新 `scripts/gen-marimo-coverage.py` 等 coverage SSOT 的 pytest 路径引用（若 pytest public_api 文件迁移导致路径变化）。

5) **收尾与门禁**
- 运行 `just qa`（或最小子集）确保：非 bench 测试、examples、以及治理脚本门禁均通过。
- 增加/更新必要的 drift-check（例如“新增字符串引用必须落在 `tests/fixtures/`”的扫描门禁）。

## Open Questions

- public API catalog 的排除清单与边界如何表达最稳妥：
  - 目录级排除（例如 `scalim/cli/**`、`scalim/vendor/**`）之外,是否还需要模块级/符号级 allow/deny（用于处理极少数“导出存在但不希望纳入用户侧回归”的场景）？
- public API 文档生成形态如何落地更符合 doc governance：
  - `docs/doc/getting-started/public-api.gen.md` 全文件生成,还是在 `public-api.md` 中使用 `AUTOGEN` 注入区块（保留少量手工说明）？
- public API catalog 的“符号级触达”粒度：
  - pytest gate 是否需要对每个 `__all__` 符号执行 `getattr` 触达,还是以“模块可导入 + `__all__` 可解析”为主,并在少数核心入口补充最小运行闭环？
