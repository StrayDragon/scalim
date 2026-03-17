## ADDED Requirements

### Requirement: CLI provides a local HTTP server for YAML DSL JSON Schemas
系统 SHALL 提供 `PROJECT_CLI_NAME yaml-dsl schema-serve` 命令,用于通过 HTTP 只读地暴露内置 YAML DSL JSON Schema.

该命令 MUST:
- 支持 `--host` 与 `--port` 参数用于绑定监听地址
- 仅允许访问内置 schema 目录(`src/IMPL_ROOT/dsl/by_yaml/schema/`)中的 `*.gen.json`
- 对任何非允许文件名、目录穿越或其它路径请求返回 404(不得退化为“静态站点”)

#### Scenario: schema-serve 可拉取 demand schema
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl schema-serve --host 127.0.0.1 --port 62831`
- **THEN** 对 `http://127.0.0.1:62831/demand.gen.json` 的 `GET` 请求返回 `200`
- **AND** 响应体为可解析的 JSON 文本

#### Scenario: schema-serve 拒绝目录穿越
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl schema-serve`
- **THEN** 对 `GET /../pyproject.toml` 或其等价 URL 编码形式的请求返回 `404`

### Requirement: CLI can upsert schema modeline in YAML files (IntelliJ compatible)
系统 SHALL 提供 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment` 命令,用于对用户给定的一组 YAML 文件插入或更新 schema modeline.

系统 MUST 识别以下两种 schema modeline:
- `# yaml-language-server: $schema=<...>`(YAML language server)
- `# $schema: <...>`(IntelliJ)

系统 MUST 统一写入 **IntelliJ 兼容格式**:

`# $schema: <schema-ref>`

该命令 MUST:
- 接受一个或多个 YAML 文件路径作为位置参数
- 在文件头部注释块内 upsert schema header:
  - 若在前 N 行(建议 N=10)内,在遇到第一行非注释内容前发现 `# yaml-language-server:` 或 `# $schema:` 行,则将其替换为期望 header
  - 否则将期望 header 插入为第一行(并在其后保留一个空行)
- 当目标文件已经包含期望 header 时,不得改写文件内容(幂等)

#### Scenario: upsert 在无 header 时插入到首行
- **GIVEN** 某 YAML 文件头部不包含 schema modeline
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --type demand <file.yaml>`
- **THEN** 该文件第一行变为 `# $schema: ...`

#### Scenario: upsert 在已有 header 但不一致时更新
- **GIVEN** 某 YAML 文件头部存在 `# yaml-language-server: $schema=/wrong/path/demand.gen.json` 或 `# $schema: /wrong/path/demand.gen.json`
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --type demand --schema-path http://127.0.0.1:62831 <file.yaml>`
- **THEN** 该文件头部的 schema header 被更新为 `# $schema: http://127.0.0.1:62831/demand.gen.json`

### Requirement: upsert-lsp-comment resolves schema reference from type + schema-path
系统 MUST 在 `upsert-lsp-comment` 中提供 `--type` 与 `--schema-path` 组合的 schema 引用解析,用于生成最终写入的 `<schema-ref>`.

解析规则:
- `--type` 默认值为 `demand`
- `--schema-path` 默认值为 `http://localhost:62831`
- `--schema-path` 允许是 base URL/base 目录,也允许是完整 schema URL/文件路径
- 若 `--schema-path` 以 `.json` 结尾,系统 MUST 将其视为完整 schema 引用并直接使用
- 否则系统 MUST 将其视为 base,并拼接 `/<type>.gen.json` 生成最终引用

#### Scenario: schema-path 为 base URL 时拼接文件名
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --type workflow --schema-path http://127.0.0.1:62831 <file.yaml>`
- **THEN** 写入的 schema header 为 `# $schema: http://127.0.0.1:62831/workflow.gen.json`

#### Scenario: schema-path 为完整 URL 时直接使用
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --schema-path http://example.invalid/custom.json <file.yaml>`
- **THEN** 写入的 schema header 为 `# $schema: http://example.invalid/custom.json`

#### Scenario: schema-path 缺省时使用 localhost 默认值
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --type demand <file.yaml>`
- **THEN** 写入的 schema header 为 `# $schema: http://localhost:62831/demand.gen.json`
