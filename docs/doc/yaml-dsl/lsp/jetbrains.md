# JetBrains 集成（LSP Support + YAML DSL LSP）

??? note "适用读者"
    - 使用 IntelliJ IDEA / PyCharm / WebStorm 等 JetBrains IDE 写 YAML DSL
    - 希望保留 JetBrains YAML plugin 的 schema 能力,同时获得 YAML DSL 的语义 diagnostics/跳转

## 0) 前置条件

- 可执行命令 `scalim-yaml-dsl-lsp` 已在 PATH 中
- IDE 已启用/安装 YAML plugin（用于 schema/结构体验）
- 安装 JetBrains Marketplace 插件：`LSP Support`（用于运行自定义 LSP server）

## 1) 最小配置（stdio）

在 `LSP Support` 的设置页中添加一个 server definition（不同 IDE/版本 UI 可能略有差异,关键词通常为 `Language Server Protocol` / `LSP Support`）：

- **Command**: `scalim-yaml-dsl-lsp`
- **Arguments**: `serve --log-level INFO`
- **Scope / File pattern**（建议）：
  - `scalim.yaml`
  - `demand/**/*.y*ml`
  - `workflow/**/*.y*ml`
- **Working directory / Root**（若可配置）：设为项目根目录（包含 `scalim.yaml` 的目录）

## 2) Schema vs LSP：推荐组合

JetBrains YAML plugin 负责结构校验/补全；YAML DSL LSP 负责语义能力（diagnostics + Python 引用跳转/hover/补全 + actions）。

建议在 YAML 文件头写入 `$schema` modeline（示例）：

```yaml
# $schema: /ABS/PATH/TO/src/scalim/dsl/by_yaml/schema/demand.gen.json
```

> 提示：仓库内提供了批量写入/更新 modeline 的 CLI（见 `docs/doc/yaml-dsl/cli-reference.gen.md` 的 `yaml-dsl upsert-lsp-comment`）。

## 3) 日志与排障

若发现 server 启动但功能不生效,优先获取 discovery 摘要：

```bash
scalim-yaml-dsl-lsp dump-discovery path/to/demo.yaml --json
```

如需更详细日志,可在 server 启动参数中加：

- `--log-level DEBUG`
- `--log-file /tmp/scalim-yaml-dsl-lsp.log`

更多排障项见：[Troubleshooting](troubleshooting.md)

