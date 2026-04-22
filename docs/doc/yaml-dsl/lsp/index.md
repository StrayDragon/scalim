# YAML DSL LSP/IDE 集成

??? note "适用读者"
    - 在编辑器里写 YAML DSL,希望获得语义 diagnostics 与 Python 引用跳转
    - 需要把 YAML DSL LSP server 接入 JetBrains 等编辑器

本仓库提供可复用的 YAML DSL LSP server（命令行入口见下文）,用于补足 “YAML schema 只能做结构校验” 的语义空白。

## 安装

需要 `Python >= 3.10`。

文档中的默认示例以 “**无需预安装二进制**” 为目标，优先推荐 `uvx`（ephemeral）模式：

```bash
uvx scalim-yaml-dsl-lsp serve --log-level INFO
```

如需固定安装（离线/更快启动），可选使用 `uv tool install`（installed）模式：

```bash
uv tool install scalim-yaml-dsl-lsp
# installed: scalim-yaml-dsl-lsp serve --log-level INFO
```

## 你会得到什么（LSP 负责）

- 语义 diagnostics（对齐 `scalim` library 语义,不依赖 shell-out CLI）
- `loader`/`call_by` 等 Python 引用的跳转（definition）/悬浮（hover）/补全（completion）
- `$import` 引用跳转（definition）/悬浮（hover）：从 `$import: <alias>.<path>` 跳到 fragment YAML 的目标 mapping key
- Quick Fix（code actions）:
  - 缺失 `scalim.yaml` 时可一键创建最小配置
  - imports 越界时可一键补 `yaml_dsl.import_roots`
  - `python_roots` 缺失时可一键补 `yaml_dsl.lsp.python_roots`

## 你不会得到什么（schema 负责）

YAML schema 插件负责结构校验/补全,本 LSP server **不替代** schema 插件生态：

- VSCode: `redhat.vscode-yaml`
- JetBrains: YAML plugin（配合 `$schema` modeline）

推荐组合：**schema 插件提供结构体验 + YAML DSL LSP 提供语义体验**。

### 关于 `$import` 与编辑器 schema 的边界

- 运行时（`scalim` library / `scalim-cli`）会在校验前展开 `imports` + `$import`，因此能看到 fragment 中声明的字段（例如 `kind`）。
- 编辑器侧的 YAML schema 校验（例如 VSCode 的 `redhat.vscode-yaml`）**不会展开 `$import`**，因此主 YAML 中形如 `{ $import: ..., ... }` 的 mapping 在校验时通常“看不到 fragment 字段”。

为了避免由此导致的假阳性红线（典型：`kind` 缺失时误触发 `if/then` 分支，误报 `Missing property budget`），本仓库的 schema 生成策略要求：

- 所有基于 `kind` 的 `if/then` 分支，在 `if` 中同时声明 `required: ["kind"]`，确保 `kind` 缺失时不会触发 then。

这让 schema 对 `$import` 形态更友好；真正的语义校验仍由 YAML DSL LSP diagnostics / CLI 在 imports expansion 后兜底。

## 统一约定（所有编辑器通用）

### 1) 启动命令（stdio）

最小启动命令：

```bash
uvx scalim-yaml-dsl-lsp serve --log-level INFO
# installed: scalim-yaml-dsl-lsp serve --log-level INFO
```

写入日志文件（推荐用于排障,避免编辑器吞掉 stderr）：

```bash
uvx scalim-yaml-dsl-lsp serve --log-level DEBUG --log-file /tmp/scalim-yaml-dsl-lsp.log
# installed: scalim-yaml-dsl-lsp serve --log-level DEBUG --log-file /tmp/scalim-yaml-dsl-lsp.log
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
uvx scalim-yaml-dsl-lsp dump-discovery path/to/demo.yaml --json
# installed: scalim-yaml-dsl-lsp dump-discovery path/to/demo.yaml --json
```

### 5) 推荐写法：长 `call_by` 用 block scalar（不丢跳转）

当 `call_by` 参数很长时,推荐用 YAML block scalar（`|`/`>`）拆成多行,便于编辑与 review；同时 LSP 仍可在 block scalar 内提供：

- `call_by` head reference 的 definition/hover/completion
- kwargs `=` 右侧 field-id 的 definition/hover/completion

示例（逗号可选；支持 Python 风格 `#` 行尾注释）：

```yaml
fields:
  is_quick:
    name: xx
    call_by: |
      ..loaders:xx(
        a=a,
        b=b,  # trailing comma optional
      )
```

团队可执行入口（类似 ruff）：

- `scalim-cli yaml-dsl format <paths...>`：幂等格式化（优先 plain scalar；不折叠 block scalar）
- `scalim-cli yaml-dsl lint --fix <paths...>`：风格 lint + safe fixes（例如去除可安全的多余引号）

若 client 支持 `workspace/executeCommand`,也可调用：

- command id: `scalim.dumpDiscovery`
- arguments: `[document_uri]`

## 按编辑器选择

- [JetBrains](jetbrains.md)
- [Troubleshooting](troubleshooting.md)
