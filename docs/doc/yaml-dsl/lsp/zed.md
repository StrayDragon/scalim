# Zed 集成（YAML DSL LSP）

??? note "适用读者"
    - 使用 Zed editor 写 YAML DSL
    - 希望在 Zed 中同时获得 schema（结构）与 YAML DSL LSP（语义）能力

## 0) 前置条件

- 二选一：
  - `uv` 已安装（`uvx` 可用，推荐）
  - 可执行命令 `scalim-yaml-dsl-lsp` 已在 PATH 中（installed 模式）
- 推荐将配置放在项目内：`<repo>/.zed/settings.json`（便于团队共享与审计）

## 1) 最小配置（stdio）

Zed 支持为语言指定 language servers,并为每个 server 配置启动命令。下面示例会在 YAML 中启用 YAML DSL LSP,同时保留默认/已注册的其它 YAML language server（通常用于 schema 结构体验）：

```json
{
  "languages": {
    "YAML": {
      "language_servers": ["scalim-yaml-dsl-lsp", "..."]
    }
  },
  "lsp": {
    "scalim-yaml-dsl-lsp": {
      "binary": {
        "path": "uvx",
        "arguments": ["scalim-yaml-dsl-lsp", "serve", "--log-level", "INFO"]
      }
    }
  }
}
```

说明：

- `language_servers` 中的 `...` 表示“保留其它已注册 server”。这有助于保留 schema/结构能力,避免把 YAML schema 插件生态替换掉。
- 若需要排障,建议先把 `--log-level` 提到 `DEBUG`,并配合 `--log-file`（见 Troubleshooting）。
  - installed 模式等价写法：
    - `path`: `scalim-yaml-dsl-lsp`
    - `arguments`: `["serve", "--log-level", "INFO"]`

## 2) YAML 文件匹配建议

最小接入通常直接对 YAML 启用即可；如果你希望限制到 YAML DSL 范围,建议按团队约定统一目录结构（例如 `demand/**`、`workflow/**`）,并在项目内配置中进行约束。

## 3) Workspace root / discovery 说明

Zed 的 workspace root 通常为你打开的文件夹。为使 discovery 结果稳定,建议：

- 以包含 `scalim.yaml` 的目录作为 workspace root 打开项目
- 若项目存在多份 `scalim.yaml`,确认 nearest-wins 的查找路径符合预期

## 4) 排障入口

优先使用 CLI dump discovery：

```bash
uvx scalim-yaml-dsl-lsp dump-discovery path/to/demo.yaml --json
# installed: scalim-yaml-dsl-lsp dump-discovery path/to/demo.yaml --json
```

更多排障项见：[Troubleshooting](troubleshooting.md)
