# YAML DSL LSP/IDE 集成

??? note "适用读者"
    - 在编辑器里写 YAML DSL,希望获得语义 diagnostics 与 Python 引用跳转
    - 需要把 YAML DSL LSP server 接入 Neovim / Zed / JetBrains 等编辑器

本仓库提供可复用的 YAML DSL LSP server（命令行入口见下文）,用于补足 “YAML schema 只能做结构校验” 的语义空白。

## 你会得到什么（LSP 负责）

- 语义 diagnostics（对齐 `scalim` library 语义,不依赖 shell-out CLI）
- `loader`/`call_by` 等 Python 引用的跳转（definition）/悬浮（hover）/补全（completion）
- Quick Fix（code actions）:
  - 缺失 `scalim.yaml` 时可一键创建最小配置
  - imports 越界时可一键补 `yaml_dsl.import_allowed_roots`
  - `python_roots` 缺失时可一键补 `yaml_dsl.editor.python_roots`

## 你不会得到什么（schema 负责）

YAML schema 插件负责结构校验/补全,本 LSP server **不替代** schema 插件生态：

- VSCode: `redhat.vscode-yaml`
- Neovim: `yaml-language-server` / `yamlls`
- JetBrains: YAML plugin（配合 `$schema` modeline）

推荐组合：**schema 插件提供结构体验 + YAML DSL LSP 提供语义体验**。

## 统一约定（所有编辑器通用）

### 1) 启动命令（stdio）

最小启动命令：

```bash
scalim-yaml-dsl-lsp serve --log-level INFO
```

写入日志文件（推荐用于排障,避免编辑器吞掉 stderr）：

```bash
scalim-yaml-dsl-lsp serve --log-level DEBUG --log-file /tmp/scalim-yaml-dsl-lsp.log
```

### 2) YAML 文件匹配/启用方式

建议让 LSP 生效的文件范围（可按团队约定调整）：

- `scalim.yaml`
- demand / workflow YAML（例如 `demand/**/*.y*ml`、`workflow/**/*.y*ml`）

### 3) Workspace root 与 project discovery（nearest-wins）

LSP 的 project discovery 以“入口 YAML”作为起点：

- 从入口 YAML 所在目录向上查找最近的 `scalim.yaml`（nearest-wins）
- 若未找到,默认以入口 YAML 所在目录作为 `project_root`

discovery 输出至少包含：

- `project_root`
- `scalim_yaml_path`（可为空）
- `python_roots`
- `allowed_yaml_roots`

### 4) 排障入口：dump discovery（推荐）

CLI（最通用,推荐作为 issue 附件）：

```bash
scalim-yaml-dsl-lsp dump-discovery path/to/demo.yaml --json
```

若 client 支持 `workspace/executeCommand`,也可调用：

- command id: `scalim.dumpDiscovery`
- arguments: `[document_uri]`

## 按编辑器选择

- [Neovim](neovim.md)
- [Zed](zed.md)
- [JetBrains](jetbrains.md)
- [Troubleshooting](troubleshooting.md)

