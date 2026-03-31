## Why

当前 Scalim YAML DSL 的“开发者写配置”编辑体验主要依赖本地 IDE/编辑器：

- 依赖 `redhat.vscode-yaml` 等通用 YAML 扩展提供的 schema 体验，但缺少 DSL 语义能力（诊断、跳转、补全、hover）以及 `loader`/`call_by` 等关键字段的工程化导航能力。

历史上仓库内曾有 `frontend/scalim-yaml-dsl-editor/` Web 编辑器实现，现已移除；后续以 LSP/IDE 集成为主路径。

与此同时,当前仓库内部虽然已经有 validator、schema 与部分路径解析能力,但还没有一套稳定的“编辑器静态语义 API”: demand validator、workflow 校验、导入展开、位置索引与 Python 引用解析分散在不同模块中,其中一些运行时解析逻辑仍带有动态导入假设,不能直接拿来做 LSP 端的静态导航.

我们希望把 DSL 的语义能力带到 VSCode（以及未来可扩展到其他编辑器），并且：

- **不替换** `redhat.vscode-yaml`（它继续负责 YAML + JSON Schema 的结构体验）。
- **不调用** `scalim-cli`（LSP 直接复用 `scalim` 包内部逻辑与 schema 资源）。
- **不重写** 通用 YAML language server（不以 Python 复刻 `yaml-language-server` 为目标）。
- 将产物做成 **独立仓库**（便于发布、复用与版本管理），但以 `scalim` 作为 library 依赖确保语义逻辑与运行时一致。

## What Changes

- **New**: 定义一套跨编辑器的“项目发现 / 文件识别 / Python roots”方案,用于识别哪些 YAML 属于 Scalim DSL,以及如何为 `loader`/`call_by` 提供静态落盘解析。
  - 该方案可以是新增配置文件（例如 `scalim.config.yaml`）,也可以复用现有项目配置/发现机制；当前 proposal 不预设唯一 SSOT 形态
  - 必须支持 `demand` vs `workflow` 的分流（决定语义诊断边界）
- 在进入实现前,应先比较“新增专用配置文件 / 复用现有项目配置 / 零配置推导”三类路径,并结合真实项目布局确认哪种 discovery 方案最稳,而不是现在就锁死配置文件形态。
- **New**: 定义 Python LSP Server（`pygls`）的 v1 语义能力边界（不走 CLI）
  - 定位为 `redhat.vscode-yaml` 之上的语义 sidecar，而不是单体式通用 YAML server
  - Diagnostics：demand 复用内部 validator + 定位；workflow v1 仅做 schema-only 校验（与当前边界对齐）
  - Go to Definition：仅对 `loader`/`call_by` 等引用字段提供跳转
  - Completion / Hover：仅在引用字符串内提供补全与解释，避免与 YAML 扩展冲突
- LSP 侧静态解析应以 library 复用为主,但不能直接照搬当前运行时路径解析实现；需要先拆出不依赖动态导入、副作用与 CLI 输出格式的静态语义层.
- **New**: 定义 VSCode 扩展 v1 行为
  - 作为 `redhat.vscode-yaml` 的协同扩展：schema 绑定 + LSP server 启动与管理
  - 读取并同步所选的项目发现/配置方案（默认零配置可用，自定义时可同步到工作区 `yaml.schemas`）
  - 负责 Python 环境管理（在 `globalStorageUri` 下维护 venv，并以 pinned 版本安装 LSP server）

## Capabilities

### New Capabilities
- `yaml-dsl-editor-project-discovery`: 定义跨编辑器通用的项目发现/文件识别/Python roots 约束,但当前不预设必须采用单独的 `scalim.config.yaml`。
- `yaml-dsl-lsp-server`: 定义 Scalim YAML DSL 的语义 LSP 能力（Diagnostics/Definition/Completion/Hover），并明确“不调用 CLI、复用 `scalim` 内部逻辑”的约束。
- `yaml-dsl-vscode-extension`: 定义 VSCode 侧与 `redhat.vscode-yaml` 协同的扩展行为（schema 绑定、配置同步、Python venv 管理与 server lifecycle）。

### Modified Capabilities
- （空）

## Impact

- 影响范围（规范层面）：
  - 本仓库：需要保证 `src/scalim/dsl/by_yaml/**` 的关键语义能力可被外部 LSP server 以 library 方式复用（不依赖 CLI 输出格式）。
  - schema 产出：LSP/扩展需要稳定获取 `demand.gen.json` / `workflow.gen.json`（可通过资源读取或发布包携带）。
  - 架构分层：通用 YAML 能力继续由现有 YAML 扩展提供；`scalim` 侧仅沉淀 DSL 语义 API 与静态引用导航能力。
- 兼容性与边界：
  - `src/scalim/` 运行时边界仍需兼容 Python 3.6；LSP server 运行时版本由 `pygls` 决定（建议 `>=3.9`，在独立仓库约束）。
  - 本提案不再考虑仓库内 Web 编辑器；编辑体验以 LSP/IDE 集成为主。
- 当前 YAML DSL 语法仍在持续演进,因此本 proposal 只固化架构边界、职责分层与 v1 能力范围,不提前冻结具体 library API、LSP payload 细节、字段级 provider 规则或配置文件精确 schema。
