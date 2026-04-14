## Why

`scalim-cli` 的 `yaml-dsl` 子命令本质是 authoring/tooling 面：校验、schema、编辑器集成等开发侧能力。将其实现长期放在 `src/scalim/` 会带来持续摩擦：

- runtime core 必须保持 Python 3.6 兼容，而 CLI 更适合使用 Python 3.10+ 的开发侧生态与依赖（例如更稳定的 jsonschema 生态与类型治理）；
- CLI 的实现与测试会把“运行时核心治理”拖重，增加维护成本与重构阻力；
- 下游使用场景中，CLI 常被当作独立工具安装与使用（并且需要更清晰的安装/依赖边界）。

我们希望把 CLI 拆成独立的 workspace 包 `packages/scalim-cli`（Python >=3.10），让 `src/scalim/` 回归“运行时核心 + 可复用 service 层”，同时继续对外提供稳定的 `scalim-cli ...` 命令体验。

## What Changes

- 新增 workspace 包：`packages/scalim-cli`（requires-python >=3.10），提供 console script `scalim-cli`。
- 将 CLI 代码从 `src/scalim/cli/**` 迁移到新包（例如 `scalim_cli/**`），并进一步薄化 CLI：仅负责 args/渲染/exit code，校验逻辑委托 `scalim` 内的 service 层（例如 `dsl/yaml_dsl/validation_service.py`）。
- **BREAKING**：
  - `scalim` 运行时发行物不再提供 `scalim-cli` 入口；
  - `scalim.cli` 模块路径不再存在（仓库内引用与测试将统一迁移到新包）。
- 重写/整理/压缩一批 CLI 相关 tests：将“校验逻辑正确性”放回 service 层测试，CLI 侧以少量高价值的行为回归（输出格式、退出码、关键子命令）覆盖。
- 更新文档中关于 CLI 安装方式与依赖边界的说明（从“主包 extras”转为“独立 CLI 发行物”）。

## Capabilities

### New Capabilities
- （无）

### Modified Capabilities
- `package-identity`: CLI 分发与安装边界收敛（`scalim-cli` 由独立发行物提供；runtime 维持 Python 3.6 最小依赖）。
- `yaml-dsl-cli-validation`: CLI 仍需满足既有校验输出/退出码/JSON contract，但实现位置迁移到 `packages/scalim-cli`，并进一步薄化（委托 service 层）。

## Impact

- 受影响代码：
  - 迁移/移除：`src/scalim/cli/**`
  - 新增：`packages/scalim-cli/**`
  - 根 `pyproject.toml`（scripts/optional-deps/dev 依赖组调整）
  - docs 中涉及 CLI 安装/用法的章节与示例
  - tests 中导入 `scalim.cli.*` 的用例与相关 fixture
- 对用户：
  - 运行时使用仍安装 `scalim`（Python >=3.6）；
  - 命令行工具需安装 `scalim-cli`（Python >=3.10）。

