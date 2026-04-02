## Context

当前 editor 语义实现位于主包 `scalim` 的运行时代码树（`src/scalim/dsl/by_yaml/editor_semantics.py`）中。
主包需要兼容 `Python 3.6`，但 editor/LSP 侧的演进更需要 `Python 3.10+` 的生态（例如更现代的依赖与类型能力），并且需要更清晰的信任边界与并发模型。

本变更希望把 editor 语义抽离为独立包，使其成为 LSP server/VSCode extension/CLI 的共享 core，同时不把主包运行时强行推向更高的 Python 版本。

## Goals / Non-Goals

**Goals:**
- 抽离 editor 语义为独立包（`requires-python >= 3.10`），并定义稳定的公共 API（discovery/diagnostics/definition/hover/completion）。
- 明确安全边界：静态解析、禁止执行用户代码、禁止污染进程级全局状态（例如 `sys.path`）。
- 提供主包侧 shim，保证在未安装新包时给出可执行的提示；安装后可无缝复用 editor API。
- 为后续加入 LSP server 预留结构（同一 distribution 内的 `core`/`server` 模块，或同名包的可选 extra）。

**Non-Goals:**
- 本变更不要求立即实现完整 LSP server（只要求抽离 core 并把 server 侧依赖路径收敛到 core）。
- 不改变 `YAML DSL` 的运行时语义/输出行为（仅重构 editor 侧组织形式）。
- 不要求新包兼容 `Python 3.6`。

## Decisions

1) **包与模块布局**
- 新增 distribution：`scalim-yaml-dsl-lsp`（目录：`packages/scalim-yaml-dsl-lsp/`）。
- import root：`scalim_yaml_dsl_lsp`。
- core 模块：`scalim_yaml_dsl_lsp.core`（或 `scalim_yaml_dsl_lsp/core/*`），承载 editor 语义的 SSOT 实现。
- 预留 server 模块：`scalim_yaml_dsl_lsp.server`（可为空壳），或通过 `extras`（例如 `scalim-yaml-dsl-lsp[server]`）引入 `pygls` 相关依赖。

2) **依赖策略**
- core 仅依赖主包 `scalim`（复用 schema、YAML 解析与 validator 逻辑），并保持对 editor 侧的依赖最小化。
- `pygls/lsprotocol` 等依赖放入可选 extra 或 server 子模块，避免把 editor core 与 IO 层强绑定。

3) **主包 shim 行为**
- 保留 `src/scalim/dsl/by_yaml/editor_semantics.py` 作为薄 shim：
  - 若 `scalim_yaml_dsl_lsp` 可导入，则从新包 re-export 公共 API；
  - 否则抛出带迁移/安装指令的错误（或返回结构化 warnings），避免 silent failure。
- shim 只包含少量运行时代码，保持 `Python 3.6` 兼容。

4) **公共 API 约束**
- editor core MUST：
  - 不执行用户代码；
  - 不修改进程级全局状态（例如 `sys.path`、`sys.meta_path`）；
  - 输出结构化、可 JSON 序列化的诊断/位置/补全结果。
- 兼容性策略：以 spec 文件定义的 API 作为 SSOT；主包 shim 只保证“可用性/错误提示”，不承诺完全兼容所有内部实现细节。

## Risks / Trade-offs

- **[Risk] 依赖与版本漂移（主包 vs core 包）** → 通过 `scalim-yaml-dsl-lsp` 依赖 `scalim` 的版本范围 + CI 集成测试保证协同升级。
- **[Risk] BREAKING：旧 import 路径不再直接可用** → 通过 shim + 清晰的错误信息/安装提示降低迁移成本。
- **[Risk] core 仍然引用主包内部实现细节** → 在 specs 中明确哪些符号是稳定 API，逐步收敛到公开边界。

## Migration Plan

1. 新建 `packages/scalim-yaml-dsl-lsp`（`pyproject.toml` + `src/scalim_yaml_dsl_lsp/`）。
2. 将现有 `editor_semantics.py` 的实现迁移到 core，并补齐测试覆盖。
3. 在主包保留 shim（可选提供 `scalim[yaml-dsl-lsp]` extra）。
4. 将 LSP server（后续变更）统一改为依赖 core（避免重复实现）。
5. 更新 docs/specs：新增/修改对应 OpenSpec spec，并确保 `just openspec-check` 通过。

## Open Questions

- core API 的命名与分层（`core` 单文件 vs 分模块）是否需要在第一版就定死？
- `scalim` 是否需要提供一个更明确的“editor 内部依赖”稳定层（例如 `scalim.dsl.by_yaml.editor_api`）以减少 core 对私有模块的耦合？
