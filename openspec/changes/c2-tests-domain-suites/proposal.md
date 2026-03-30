## Why

当前 `tests/` 主要以“平铺文件 + 文件名前缀”组织（约 200+ 个 `test_*.py`，收集用例约 2000+），在 execution/workflow/YAML DSL 能力持续重构的背景下暴露出明显维护成本：

- **可定位性差**：同一领域能力（例如 YAML DSL / workflow / execution）相关用例散落在大量文件中，新增/排错时需要先“全局搜一遍”才能找到入口。
- **重叠与无效覆盖增多**：存在大量“分支覆盖驱动”的用例与“契约/用户视角”用例混在一起，导致重复脚手架与重复断言扩散（典型信号：`*_additional.py`、`*_coverage.py`、`cover_branches` 命名、以及少数超大测试文件聚合多类场景）。
- **公共 API 覆盖与文档易漂移**：当前 public API 覆盖分散在 pytest 的导入冒烟与 `notebooks/marimo/example_public_api_suite/` 的示例章节之间；文档侧对“公开导出面”的描述也容易与代码实际 `__all__` 产生漂移，导致贡献者难以判断“哪些导出必须被回归覆盖、哪些属于内部实现”。

本变更目标不是把测试结构绑定到 `src/scalim/**` 的实现路径（内部会频繁重构），而是用**领域（domain）**作为稳定组织维度：让贡献者从“用户视角/核心链路能力”进入测试套件，同时保持 `src/scalim` 的 **100% 覆盖率门禁**不降级。

## What Changes

- 将 `tests/` 重组为**领域套件（domain suites）**目录结构（不要求与 `src/scalim` 包路径一致），至少包含：
  - `public_api/`：面向用户的 public API + 核心链路 API pytest 套件（覆盖范围由扫描 `src/scalim/**` 中 `__all__` 导出自动生成）
  - `yaml_dsl/`：YAML DSL（解析/校验/转换/模板变量/输出配置等）
  - `workflow/`：workflow 运行时（编排、cache_pool、resources、可见性规则等）
  - `execution/`：执行链路（`run_ir`/engine/pipeline/operators/adaptive 等）
  - `planning/`、`sinks/`、`ob/`（含 events/hooks/observer）等其它核心领域
  - `governance/`：质量门禁/结构护栏类测试（module layout、API surface、scripts checks、OpenSpec sanitize 等）
  - `integration/`：真实 demo/慢测（延续 `@pytest.mark.slow` 约定）
  - `bench/` 保持现状（继续用 `bench` marker + bench-only 入口）
- 抽出并收敛重复脚手架：
  - `tests/support/`：纯测试辅助工具（不被 YAML `loader:`/`call_by:` 字符串引用）
  - `tests/fixtures/`：稳定的 loader/call_by fixture 模块与 YAML 夹具（**一次性迁移**所有字符串引用入口到该目录,不保留旧路径兼容）
- 去重与覆盖策略调整（不降低 100% 覆盖率）：
  - 将“分支覆盖驱动”用例显式归类（例如归入各 domain 的 `coverage/` 子域或单独域），并优先用参数化/共享断言减少重复。
  - 合并/消除 `*_additional.py` 造成的主题分散：同一能力的契约用例收敛到同一 domain 下，避免“同一 SSOT 被多处重复断言”。
  - 对超大测试文件按场景拆分（例如 workflow/YAML DSL 的多类场景拆成多个文件），但保持断言语义与覆盖率门禁不变。
- public API “双门禁对齐”（两条链路都覆盖,且共享同一份自动生成的覆盖范围定义）：
  - **覆盖范围 SSOT**：扫描 `src/scalim/**` 中所有声明了 `__all__` 的模块与导出符号（排除 `cli/`、`vendor/` 等个别目录/模块），生成可审计的 public API catalog。
  - `pytest`：`tests/public_api/` 对 catalog 中的模块/符号做导入与 `__all__` 解析回归,并覆盖核心链路的最小运行闭环。
  - `just examples`：`notebooks/marimo/example_public_api_suite/` 继续覆盖同一份 catalog 对应的用户侧示例（教学/叙事/扩展点演示），并通过 gate 输出可定位 summary。
- 文档自动生成化：
  - 将 public API 导入指南与导出清单改为由 public API catalog 自动生成的 `*.gen.md`（作为用户侧可读 SSOT 投影），并纳入 `just gen-docs`/drift-check。
- 为应对上游 main 变动导致的提案过期风险：实施按“先调研后搬迁”的节奏推进（先完成 inventory + domain 归类规则，再按 domain 小批量迁移），并坚持一次性升级引用（不保留旧路径兼容 stub）。

## Capabilities

### New Capabilities
- `tests-domain-suites`: 定义测试套件的 domain 组织、重复治理规则、以及“可被 allowlist 字符串引用的 fixture 模块”的稳定边界与目录约定。

### Modified Capabilities
- `testing-quality`: 增补“domain suites”组织与重复治理要求；并明确 `pytest` 与 `just examples` 都必须覆盖由 `__all__` 扫描生成的 public API catalog,同时保持 `src/scalim` 覆盖率门禁为 100%。
- `marimo-example-public-api-suite`: 扩展并明确 public API suite 的覆盖范围必须与 public API catalog 对齐（与 pytest public_api 套件共同形成两个投影）。
- `public-api-manifest`: public API 文档与推荐导入清单从“手工维护”迁移为“从 `__all__` 扫描自动生成的 `.gen.md`”,并纳入 drift-check。

## Impact

- 受影响代码/配置：
  - `tests/`：大量文件移动/重命名/拆分；公共 fixture/support 的抽取与复用；coverage-only 用例的归类与去重。
  - `pyproject.toml` 与 `justfile`：总体 gate 语义不变（默认非 bench + 100% cov；bench 单独入口），但可能新增更清晰的 suite 入口（例如 `just test-public-api`/`pytest -k public_api` 的友好约定）。
  - `notebooks/marimo/example_public_api_suite/`：章节覆盖范围与 pytest public_api 套件对齐，避免“示例与 pytest 漂移”。
  - `docs/doc/getting-started/`：public API 导入指南将迁移为 `*.gen.md`（由扫描结果生成），并通过 `just gen-docs`/`just docs-drift-check` 治理漂移。
- 风险与约束：
  - 测试 YAML 中存在大量 `loader:`/`call_by:` 的字符串引用与 `allowed_modules` 白名单：迁移必须一次性升级所有引用（不做旧路径兼容），并将这些引用集中到 `tests/fixtures/` 的稳定边界内。
  - 目录搬迁可能引入 merge 冲突：按 domain 分批迁移、每批保持语义等价与门禁全绿，以降低与上游 main 漂移的耦合面。
