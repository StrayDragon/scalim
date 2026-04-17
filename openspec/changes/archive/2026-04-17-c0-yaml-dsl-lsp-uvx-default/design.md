## Goals

- 把 YAML DSL LSP 的“默认接入方式”统一为 **uvx 启动**：
  - 用户复制文档中的最小配置即可运行,不要求提前安装 `scalim-yaml-dsl-lsp` 二进制。
  - 保持对不同编辑器配置模型（单字符串命令 / binary+args 列表）的兼容与一致性。
- 同时提供“固定安装”路径作为可选方案（面向离线/低启动开销/长期环境）。

## Non-goals

- 不修改 LSP 的语义能力范围（diagnostics/跳转/hover/补全/actions 等不在此变更中扩展）。
- 不引入新的安装器/包管理器依赖（继续以 uv/uvx 为推荐）。

## Proposed docs conventions

### 1) Two supported launch modes

文档统一描述两种模式（按推荐优先级排序）：

1. **Ephemeral（默认推荐）**：`uvx scalim-yaml-dsl-lsp serve --log-level INFO`  
   - 优点：无需预安装；复制即用；适合试用/临时环境/容器排障  
   - 注意：首次启动需要联网下载（但 uv 有缓存）；需要 `uv/uvx` 在 PATH

2. **Installed（可选）**：`uv tool install scalim-yaml-dsl-lsp` + `scalim-yaml-dsl-lsp serve ...`  
   - 优点：启动更快；更适合离线/稳定环境  
   - 注意：需要一次性安装

### 2) Editor config patterns

由于不同编辑器对配置形态不同,文档对每个 editor 都给出两套等价模板:

- **uvx 模板（默认）**
  - 如果 editor 支持 “command + args 列表”：
    - command: `uvx`
    - args: `["scalim-yaml-dsl-lsp", "serve", "--log-level", "INFO"]`
  - 如果 editor 只支持一个 shell 命令字符串：
    - command: `uvx scalim-yaml-dsl-lsp serve --log-level INFO`

- **installed 模板（备选）**
  - command: `scalim-yaml-dsl-lsp`
  - args: `["serve", "--log-level", "INFO"]`

### 3) Troubleshooting commands

所有 troubleshooting 页面的命令示例提供 uvx 版本优先（并用注释给出 installed 版本）,例如:

- dump discovery:
  - `uvx scalim-yaml-dsl-lsp dump-discovery path/to/demo.yaml --json`
  - （installed）`scalim-yaml-dsl-lsp dump-discovery path/to/demo.yaml --json`

## File-level plan (docs)

建议调整的文档点位（以“默认改为 uvx” 为主）：

- `docs/doc/yaml-dsl/lsp/neovim.md`
  - 前置条件改为：`uvx` 可用（或二进制在 PATH 两选一）
  - `cmd` 示例默认使用 `{"uvx", "scalim-yaml-dsl-lsp", "serve", ...}`
- `docs/doc/yaml-dsl/lsp/zed.md`
  - `binary.path` 默认设置为 `uvx`
  - `arguments` 前置插入 `scalim-yaml-dsl-lsp`
- `docs/doc/yaml-dsl/lsp/jetbrains.md`
  - `LSP Support` 的 Command 改为 `uvx`
  - Arguments 改为 `scalim-yaml-dsl-lsp serve --log-level INFO`
- `docs/doc/yaml-dsl/lsp/troubleshooting.md`
  - 所有 `scalim-yaml-dsl-lsp ...` 命令增加 uvx 等价写法（优先展示 uvx）

最后统一通过 `just gen-docs` 刷新 `docs/site/**`。

## Optional: LSP CLI message tweak

当前 `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/cli.py` 在依赖缺失时提示:

- `uv tool install scalim-yaml-dsl-lsp`

建议补充一行 uvx 兜底提示,降低排障门槛:

- `uvx scalim-yaml-dsl-lsp serve --log-level INFO`

该变更不影响功能,仅改善可用性与一致性。

## Rollout / Compatibility

- 文档变更为软变更；不会影响现有已安装二进制用户。
- `uvx` 启动方式依赖用户安装 uv；文档需明确这一前置条件。

