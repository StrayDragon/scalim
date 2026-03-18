## MODIFIED Requirements

### Requirement: CLI can upsert schema modeline in YAML files (IntelliJ compatible)
系统 SHALL 提供 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment` 命令,用于对用户给定的一组 YAML 文件插入或更新 schema modeline,以改善编辑器/LSP 的补全与诊断体验。

系统 MUST 识别以下两种 schema modeline:
- `# yaml-language-server: $schema=<...>`(Red Hat YAML Language Server)
- `# $schema: <...>`(IntelliJ)

系统 MUST 支持通过 `--comment-style {all,jetbrains,redhat}` 控制写入风格:
- `all`(默认): 同时 upsert 两种 modeline
- `jetbrains`: 仅 upsert `# $schema: <schema-ref>`
- `redhat`: 仅 upsert `# yaml-language-server: $schema=<schema-ref>`

该命令 MUST:
- 接受一个或多个 YAML 文件路径作为位置参数
- 在文件头部注释块内 upsert schema header:
  - 若在前 N 行(建议 N=10)内,在遇到第一行非注释内容前发现任意一种 schema modeline,则按 `--comment-style` 期望结果进行更新/移除/去重
  - 否则将期望的 schema modeline(一个或两个)插入为文件第一行开始的注释块,并在最后一个 schema modeline 后保留一个空行
- 当目标文件已经包含期望的 schema modeline(集合与内容均一致)时,不得改写文件内容(幂等)

#### Scenario: comment-style=all 时插入两种 header
- **GIVEN** 某 YAML 文件头部不包含 schema modeline
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --comment-style all --type demand <file.yaml>`
- **THEN** 该文件头两行依次为:
  - `# yaml-language-server: $schema=.../demand.gen.json`
  - `# $schema: .../demand.gen.json`

#### Scenario: comment-style=jetbrains 时只保留 IntelliJ header
- **GIVEN** 某 YAML 文件头部包含两种 schema modeline
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --comment-style jetbrains --type demand <file.yaml>`
- **THEN** 文件头部仅保留 `# $schema: .../demand.gen.json`
- **AND** 不再包含 `yaml-language-server` modeline

#### Scenario: comment-style=redhat 时只保留 yaml-language-server header
- **GIVEN** 某 YAML 文件头部包含两种 schema modeline
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --comment-style redhat --type demand <file.yaml>`
- **THEN** 文件头部仅保留 `# yaml-language-server: $schema=.../demand.gen.json`
- **AND** 不再包含 `# $schema:` modeline

### Requirement: upsert-lsp-comment resolves schema reference from type + schema-path
系统 MUST 在 `upsert-lsp-comment` 中提供 `--type` 与 `--schema-path` 组合的 schema 引用解析,用于生成最终写入的 `<schema-ref>`.

解析规则:
- `--type` 默认值为 `demand`
- `--schema-path` 默认值为内置 schema 目录的本地绝对路径(即 `src/IMPL_ROOT/dsl/by_yaml/schema/` 在包内的实际路径)
- `--schema-path` 允许是 base URL/base 目录,也允许是完整 schema URL/文件路径
- 若 `--schema-path` 以 `.json` 结尾,系统 MUST 将其视为完整 schema 引用并直接使用
- 否则系统 MUST 将其视为 base,并拼接 `/<type>.gen.json` 生成最终引用

#### Scenario: schema-path 为 base URL 时拼接文件名
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --type workflow --schema-path http://127.0.0.1:62831 <file.yaml>`
- **THEN** 写入的 schema ref 以 `/workflow.gen.json` 结尾

#### Scenario: schema-path 为完整 URL 时直接使用
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --schema-path http://example.invalid/custom.json <file.yaml>`
- **THEN** 写入的 schema ref 为 `http://example.invalid/custom.json`

#### Scenario: schema-path 缺省时使用内置 schema 目录默认值
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --type demand <file.yaml>`
- **THEN** 写入的 schema ref 以 `/demand.gen.json` 结尾

## REMOVED Requirements

### Requirement: CLI provides a local HTTP server for YAML DSL JSON Schemas
**Reason**: schema 引用可以直接使用本地绝对/相对路径或 URL; 维护一个内置 HTTP server 会扩大维护面并制造额外的“先启动服务再写入 modeline”的隐式前置条件。

**Migration**: 使用 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment` 直接写入本地 schema 路径(默认即使用内置 schema 目录),或显式指定 `--schema-path <dir-or-url>` 以匹配你的编辑器/LSP 解析方式。
