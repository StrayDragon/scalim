## Context

当前仓库内已经生成并内置了 YAML DSL 的 JSON Schema(`src/scalim/dsl/by_yaml/schema/*.gen.json`),也已经提供了 CLI 辅助命令用于校验与发现 schema(例如 `yaml-dsl schema validate/show/path`)。
但在 IDE/LSP(例如 VS Code 的 `yaml-language-server`) 场景下,用户仍需要手工把 schema 路径写进 YAML 顶部的 `$schema` 注释,而路径往往是:

- 仓库相对路径(对文件目录结构敏感,复制到其它目录就失效)
- `.venv/site-packages/...` 的绝对路径(难以共享/易漂移)

本设计在不引入新依赖、不改变现有校验命令行为的前提下,补齐两块“就地可用”的工程化能力:

1) **schema-serve**: 用 stdlib `http.server` 把内置 schema 以 HTTP 形式暴露出来,便于 `$schema=http://127.0.0.1:.../demand.gen.json` 直接被 LSP 拉取。
2) **upsert-lsp-comment**: 对用户给定的一组 YAML 文件,自动插入/更新 `# yaml-language-server: $schema=...` 头部,避免手工维护。

约束:
- 运行时兼容 Python 3.6
- CLI 现状使用 `argparse`(`src/scalim/cli/yaml_dsl.py`),新增命令需保持一致风格
- schema 文件是生成物(`*.gen.json`),不得手工修改;本变更只消费它们

## Goals / Non-Goals

**Goals:**
- 提供 `PROJECT_CLI_NAME yaml-dsl schema-serve` 一键启动本机 schema HTTP server,默认端口固定且易复制。
- server 必须“只暴露 schema”: 任何目录穿越/非 schema 文件访问都返回 404,不得意外把仓库当作静态站点暴露。
- 提供 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment` 对一组 YAML 文件批量 upsert `$schema` 头部:
  - 已存在则更新(不一致才写)
  - 不存在则插入到文件第一行
  - 对已是最新的文件不写入(保证幂等)
- 默认 schema-path 指向本机 schema-serve,使“启动 server → 一键写入 header”成为最短路径。

**Non-Goals:**
- 不实现长期驻留/后台 daemon/自动开机自启等能力(仍由用户自行启动命令)。
- 不提供公网可访问的 schema 服务,不做认证/鉴权。
- 不修改或重新生成 `*.gen.json` schema 产物。
- 不强制改写仓库内的示例 YAML(避免把本机 URL 固化进共享样例)。

## Decisions

### Decision: schema-serve 不提供 index,仅在启动时打印可用 schema 与 URL

原因:
- index 本身会引入额外的稳定性承诺(输出格式、排序、字段含义),且对 YAML LSP 的核心目标价值有限。
- 通过启动时打印(并提示典型 `$schema=` 写法)即可满足“复制粘贴到 YAML”与“团队统一 workaround”需求,实现也更简单。

约定:
- schema-serve 启动后 MUST 打印当前可用的 `*.gen.json` 文件名列表与可复制 URL
- 不提供 `/` 或 `/index.json` 等受控 index endpoint

### Decision: schema-serve 使用自定义 request handler 而不是直接 `python -m http.server`

原因:
- Python 3.6 的 `SimpleHTTPRequestHandler` 不支持 `directory=...` 参数,直接复用会倾向于以 CWD 提供静态文件,风险较高。
- 我们需要明确的 allowlist(仅 `*.gen.json`),并在 handler 里拒绝任何非预期路径,同时避免 URL 编码绕过。

实现要点(非逐行实现):
- 将 schema 根目录固定为 `Path(__file__).resolve().parents[1] / "dsl/by_yaml/schema"`(与现有 `_default_schema_path()` 一致来源)
- 允许的文件名集合来自该目录下的 `*.gen.json`(例如 `demand.gen.json`/`workflow.gen.json`)
- handler 对请求路径做严格解析:
  - 只接受形如 `/<filename>` 的单段路径
  - filename 必须在 allowlist 且以 `.gen.json` 结尾
  - 否则返回 404
- 仅实现 `GET`/`HEAD`;其它方法返回 405

### Decision: upsert-lsp-comment 的 header 识别范围限定为“文件头部注释块”

原因:
- 在文件中部出现同样的注释会造成误替换。
- 前端编辑器(`frontend/scalim-yaml-dsl-editor`)已经采用“只扫描前 10 行/直到遇到第一行非注释内容”为准的策略,CLI 应保持一致。

行为约定:
- 在前 N 行(建议 N=10)内,按顺序扫描:
  - 若遇到 `# yaml-language-server:` 行,则将该行替换为期望 header 并立即结束(仅当不一致时写入)
  - 若遇到第一行非空且非 `#` 开头内容,停止扫描并视为“无 header”
- 若无 header,则把 header 插入为第一行,并在其后补一个空行(保持可读性)

### Decision: `--schema-path` 支持“base URL/dir”与“full URL/file”两种输入

为了贴合用户常见心智(`127.0.0.1:62831/<schema名>`),将 `--schema-path` 解释为“base”更顺手,但也必须允许用户传入完整 URL/文件路径。

解析策略:
- 若 `--schema-path` 以 `.json` 结尾,视为完整 schema 引用,直接使用
- 否则视为 base,按 `/<type>.gen.json` 进行拼接:
  - URL base: `http://127.0.0.1:62831` + `/demand.gen.json`
  - dir base: `/abs/path/to/schema` + `demand.gen.json`

## Risks / Trade-offs

- [默认 host=0.0.0.0 可能在局域网暴露端口] → handler 严格限制只 serve schema;同时 CLI 输出中提示用户在不需要跨机访问时使用 `--host 127.0.0.1`
- [用户把本机 URL header 提交进共享仓库] → upsert 默认使用 `http://localhost:62831/...`(避免写入 `0.0.0.0`),且仅对显式传入的文件生效;文档/示例不强制写入;并在 CLI 输出中提示“用于本机 LSP,不建议提交”
- [Windows 路径/换行差异导致 header 插入格式不统一] → 写入统一使用 `\n` 并保持纯文本处理;必要时在测试中覆盖 `\r\n` 输入
- [schema 文件名未来新增] → server 与 upsert 通过扫描 `*.gen.json`/`<type>.gen.json` 约定天然可扩展,无需硬编码列表

## Migration Plan

1. 实现 `yaml-dsl schema-serve` 并增加最小 e2e 测试(启动 server → 拉取 schema → 断言 200/JSON)。
2. 实现 `yaml-dsl upsert-lsp-comment` 并增加覆盖测试(插入/更新/幂等/遇到内容行停止扫描)。
3. (可选)更新 docs/skill 中的 LSP 配置指引,并遵循文档治理规则:
   - 不直接修改 `.gen.` 文件或 injected block 内部
   - 若触及 docs 生成块,以 SSOT 修改后运行 `just gen-docs`

## Open Questions

- (无)
