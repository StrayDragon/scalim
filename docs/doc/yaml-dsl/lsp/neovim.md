# Neovim 集成（YAML DSL LSP）

??? note "适用读者"
    - 使用 Neovim（内置 LSP client）写 YAML DSL
    - 希望同时保留 schema 插件（结构体验）与 YAML DSL LSP（语义体验）

## 0) 前置条件

- 可执行命令 `scalim-yaml-dsl-lsp` 已在 PATH 中
- 推荐使用 `nvim-lspconfig` 管理 LSP 配置

> 提示：本 LSP server 只做语义能力（diagnostics/跳转/hover/补全/actions）,schema 仍建议交给 `yaml-language-server`。

## 1) 最小配置（stdio）

下面示例会在打开 `yaml` filetype 时启动 server,并将 workspace root 尽量定位到 `scalim.yaml`（找不到则回退到 `.git` 或当前工作目录）。

```lua
local lspconfig = require("lspconfig")
local util = require("lspconfig.util")

-- 你也可以把它放到 lspconfig.configs 里注册自定义 server
lspconfig.scalim_yaml_dsl_lsp = {
  default_config = {
    cmd = { "scalim-yaml-dsl-lsp", "serve", "--log-level", "INFO" },
    filetypes = { "yaml" },
    root_dir = util.root_pattern("scalim.yaml", ".git"),
    single_file_support = true,
  },
}

lspconfig.scalim_yaml_dsl_lsp.setup({})
```

## 2) YAML 文件匹配建议

如果你不希望对所有 YAML 都启动 YAML DSL LSP,可以按目录/路径做限制（示例思路）：

- 仅对 `demand/**/*.y*ml`、`workflow/**/*.y*ml`、`scalim.yaml` 启用
- 其它 YAML 仅启用 `yaml-language-server`

不同团队对 YAML 目录结构的约定不同,建议把规则收敛到一个地方（例如 Neovim 的 autocmd 或项目级配置）。

## 3) Workspace root / discovery 说明

Neovim 的 `root_dir` 会影响 server 的 workspace root。推荐优先以 `scalim.yaml` 定位,以避免：

- `project_root` 不一致导致 `python_roots` 推断不稳定
- imports 的 `allowed_yaml_roots` 与预期不一致

## 4) 日志与排障

推荐通过 `--log-file` 输出日志到文件,方便从编辑器外部查看：

```bash
scalim-yaml-dsl-lsp serve --log-level DEBUG --log-file /tmp/scalim-yaml-dsl-lsp.log
```

排障时优先附上 discovery 摘要：

```bash
scalim-yaml-dsl-lsp dump-discovery path/to/demo.yaml --json
```

更多排障项见：[Troubleshooting](troubleshooting.md)

