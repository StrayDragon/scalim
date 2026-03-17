## Why

当前 YAML DSL 的 schema modeline 头部(例如 IntelliJ 兼容的 `# $schema: ...`,或 legacy 的 `# yaml-language-server: $schema=...`)通常需要引用仓库内的相对路径(例如 `../../../../src/scalim/dsl/by_yaml/schema/demand.gen.json`)或本机 `.venv/site-packages/...` 的绝对路径。
这两类路径都很脆弱: 对文件位置/运行环境高度敏感,也不利于把 YAML 配置复制到其它目录、仓库或机器上继续获得一致的 LSP 体验。

我们需要一个“就地可用”的 schema 分发机制,以及一个能批量检查/写入/更新 `$schema` 注释头的 CLI 工具,把 YAML authoring 的 IDE 配置成本降到最低,并减少因为 schema 路径错误导致的校验/补全失效。

## What Changes

- **New**: `scalim-cli yaml-dsl schema-serve` — 使用 Python stdlib `http.server` 启动只读 HTTP server,仅 serve 代码内 `src/scalim/dsl/by_yaml/schema/` 下的 `*.gen.json`
  - 参数:
    - `--port` 默认 `62831`
    - `--host` 默认 `0.0.0.0`
  - 保护策略(必须满足“只暴露 schema”):
    - 禁止目录穿越(不得通过 `..` 或 URL 编码绕过)
    - 仅允许访问 schema 目录内的 `*.gen.json` 文件(例如 `demand.gen.json`/`workflow.gen.json`)
    - 不暴露仓库其它路径;不允许任意静态文件访问

- **New**: `scalim-cli yaml-dsl upsert-lsp-comment` — 批量检查并按需写入/更新 YAML 文件的 schema modeline 头部(兼容 IntelliJ)
  - 参数:
    - `--type` schema 类型,默认 `demand`(预期支持 `demand|workflow|...`)
    - `--schema-path` schema 的路径或 URL;默认指向本机 `schema-serve`(例如 `http://localhost:62831/demand.gen.json`)
    - `paths` 一个或多个 YAML 文件路径
  - 行为:
    - 同时识别以下两种 modeline:
      - `# yaml-language-server: $schema=<...>`(YAML language server)
      - `# $schema: <...>`(IntelliJ)
    - 若文件头部存在上述任一 schema modeline,则将其替换为 **IntelliJ 兼容格式** `# $schema: <...>`(不匹配才写入)
    - 若不存在,则插入到文件第一行
    - 输出哪些文件被修改/哪些文件已是最新

- **Non-breaking**: 不改变现有 `scalim-cli yaml-dsl validate` 与 `scalim-cli yaml-dsl schema validate/show/path` 的行为与输出格式;不改变 schema 生成产物与路径。

## Capabilities

### New Capabilities
- (无)

### Modified Capabilities
- `yaml-dsl-cli-validation`: 扩展 YAML DSL CLI 命令集合,新增 schema 的本机 HTTP serve 能力与 LSP header 的批量 upsert,用于改善 IDE/LSP 体验并降低 `$schema` 路径配置成本。

## Impact

- 受影响代码:
  - `src/scalim/cli/yaml_dsl.py`(新增子命令与参数解析)
  - 可能新增轻量实现模块(用于 HTTP server 与注释头读写逻辑)
- 用户工作流:
  - 本地运行 `scalim-cli yaml-dsl schema-serve` 后,用户可在 YAML 顶部使用 `# $schema: http://localhost:62831/<schema>.gen.json`
  - 通过 `scalim-cli yaml-dsl upsert-lsp-comment ...` 批量修复/插入头部,避免手工编辑与路径错误
- 文档/指引:
  - 需要在 YAML DSL 的文档或指引中补充新命令示例(不强制与本 change 同步实施,但应在落地时更新)。
