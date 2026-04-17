## Why

`packages/scalim-yaml-dsl-lsp` 已作为独立包发布到 PyPI,并提供稳定的可执行入口 `scalim-yaml-dsl-lsp`。  
但当前 editor 集成文档与默认示例仍倾向于假设该二进制已安装并在 PATH 中,这会带来两个现实问题:

- **接入门槛偏高**：团队成员需要先完成全局/工具安装,再去配置 editor；对“只想先试一下/临时环境/CI 容器排障”等场景不友好。
- **默认配置不够“可复制”**：不同编辑器对“command + args”的配置方式不同,一旦涉及安装路径/虚拟环境,文档示例容易在团队内漂移。

既然 `uv` / `uvx` 已是本仓库推荐的 Python 工具链,而 `uvx <tool> ...` 可以以“无需预安装”的方式启动 LSP server,我们可以把**默认集成方式**收敛为:

- 默认配置直接用 `uvx scalim-yaml-dsl-lsp serve ...` 启动（stdio）
- 同时保留 `uv tool install scalim-yaml-dsl-lsp` 作为“固定安装/离线/低启动开销”的可选路径

## What Changes

- 更新 YAML DSL LSP 的 editor integration guides,将默认/最小配置从 “`scalim-yaml-dsl-lsp` 在 PATH 中” 调整为 “使用 `uvx` 启动”。
  - Neovim / Zed / JetBrains（LSP Support）等示例统一给出 `uvx` 版本的 command/args 写法。
  - 同时保留已安装二进制的配置作为替代方案（并明确适用场景）。
- 补齐 troubleshooting 文档中的命令示例,优先给出 `uvx` 版本（并保留直接执行版本）。
- （如需）调整 `scalim-yaml-dsl-lsp` CLI 的错误提示文案,在依赖缺失时除了 `uv tool install` 外也提示 `uvx` 的一键运行方式。

## Capabilities

### New Capabilities

（无新增独立 capability；本变更主要是对“发布后可运行方式”的文档与默认集成策略对齐。）

### Modified Capabilities

- `yaml-dsl-lsp-editor-integration-guides`: 默认集成方式从“PATH 二进制”收敛到 “uvx 启动”,并给出各编辑器一致的配置模板。
- `yaml-dsl-lsp-serve`: 明确“如何启动 server”在文档中的推荐路径（`uvx` / `uv tool install`）与约束（Python>=3.10, stdio 为默认）。

## Impact

- **Docs（主要变更面）**
  - 影响文件: `docs/doc/yaml-dsl/lsp/*.md`（Neovim/Zed/JetBrains/Troubleshooting 等）。
  - 生成物提示: `docs/site/**` 为构建产物,不手改；通过 `just gen-docs` 刷新站点页面。
- **LSP 包（可选变更面）**
  - 可能影响: `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/cli.py`（错误提示/安装建议文案）。
  - 发布与运行前置: `scalim-yaml-dsl-lsp` 依赖 Python>=3.10（已在 package metadata 中声明）。

