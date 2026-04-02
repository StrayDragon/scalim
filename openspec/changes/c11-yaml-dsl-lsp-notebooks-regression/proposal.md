## Why

当前 editor/LSP 语义 core 已抽离为 `scalim-yaml-dsl-lsp`，但如果回归只覆盖“合成 YAML”，很容易在真实目录结构、跨文件 imports、以及 Python 引用形态（`call_by: "ref(args...)"`）上出现回归而不自知。

仓库 `notebooks/.../declared_yaml_dsl/` 维护了一套“真实且持续演进”的 YAML fixtures。将其复用为静态回归输入，可以以较低成本换取高价值稳定性，并为后续 server/IDE 集成提供可审计基线。

## What Changes

### P0（必须）
- 新增一套基于 notebooks fixtures 的 pytest 回归（不执行用户代码、不 shell-out CLI）：
  - 自动发现并遍历 fixtures 根目录下的 `*.yaml/*.yml`：
    - MUST 排除 `.tmp/**`、`scalim.yaml`、以及 `_shared/**`/`*_fragments.yaml` 等“非完整 demand/workflow”片段文件
  - 对每个“完整 YAML”运行 core diagnostics：要求 **无 errors**（warnings 允许，但必须结构健全且可定位）
  - 从 YAML 中抽取 Python 引用（至少覆盖 `loader`/`call_by`/`retry.should_retry`），回归 definition + hover + completion：
    - 允许返回空结果，但 MUST 不崩溃、并提供可诊断 warnings

### P1（建议）
- 为 fixtures 增补最小 `scalim.yaml`（位于 fixtures 根目录），用于 editor project discovery：
  - `yaml_dsl.import_allowed_roots`：允许 fixtures 内部跨子目录 imports（例如 `support/` 引用 `../_shared/...`）
  - `yaml_dsl.editor.python_roots` 建议不强依赖（当前 `scalim.yaml` roots 解析要求路径不越界 project_root）；pytest 侧可显式注入 python_roots 用于静态解析回归

## Capabilities

### New Capabilities
- `yaml-dsl-lsp-notebooks-regression`: 复用 notebooks YAML fixtures 作为 editor-semantics/LSP core 的静态回归 gate（diagnostics + definition/hover/completion）。

### Modified Capabilities
- （无；本提案只新增回归门禁，不改变运行时语义）

## Impact

- 受影响代码/资产：
  - `tests/`：新增回归测试模块
  - `notebooks/.../declared_yaml_dsl/`：可能新增最小 `scalim.yaml`（仅用于 editor discovery，不改变示例 YAML 的 SSOT 语义）
  - `packages/scalim-yaml-dsl-lsp/`：若回归暴露 `call_by(ref(args...))` 等形态缺口，可能需要小幅加固 core 的静态解析
