## Why

当前 Scalim YAML DSL 的“开发者写配置”编辑体验主要依赖本地 IDE/编辑器：

- 依赖 `redhat.vscode-yaml` 等通用 YAML 扩展提供的 schema 体验，但缺少 DSL 语义能力（诊断、跳转、补全、hover）以及 `loader`/`call_by` 等关键字段的工程化导航能力。

历史上仓库内曾有 `frontend/scalim-yaml-dsl-editor/` Web 编辑器实现，现已移除；后续以 LSP/IDE 集成为主路径。

我们希望把 DSL 的语义能力带到 VSCode（以及未来可扩展到其他编辑器），并且：

- **不替换** `redhat.vscode-yaml`（它继续负责 YAML + JSON Schema 的结构体验）。
- **不调用** `scalim-cli`（LSP 直接复用 `scalim` 包内部逻辑与 schema 资源）。
- 将产物做成 **独立仓库**（便于发布、复用与版本管理），但以 `scalim` 作为 library 依赖确保语义逻辑与运行时一致。

## What Changes

- **New**: 定义跨编辑器通用配置 `scalim.config.yaml`（SSOT）
  - 识别哪些 YAML 文件属于 Scalim DSL
  - 区分 `demand` vs `workflow`（决定语义诊断边界）
  - 定义 Python roots（供静态解析 `loader`/`call_by` 引用落盘定位）
- **New**: 定义 Python LSP Server（`pygls`）的 v1 语义能力边界（不走 CLI）
  - Diagnostics：demand 复用内部 validator + 定位；workflow v1 仅做 schema-only 校验（与当前边界对齐）
  - Go to Definition：仅对 `loader`/`call_by` 等引用字段提供跳转
  - Completion / Hover：仅在引用字符串内提供补全与解释，避免与 YAML 扩展冲突
- **New**: 定义 VSCode 扩展 v1 行为
  - 作为 `redhat.vscode-yaml` 的协同扩展：schema 绑定 + LSP server 启动与管理
  - 读取并同步 `scalim.config.yaml`（默认零配置可用，自定义时可同步到工作区 `yaml.schemas`）
  - 负责 Python 环境管理（在 `globalStorageUri` 下维护 venv，并以 pinned 版本安装 LSP server）

## Capabilities

### New Capabilities
- `yaml-dsl-editor-config`: 新增 `scalim.config.yaml`（跨编辑器通用；文件识别 + demand/workflow 分流 + python roots + LSP 行为开关）。
- `yaml-dsl-lsp-server`: 定义 Scalim YAML DSL 的语义 LSP 能力（Diagnostics/Definition/Completion/Hover），并明确“不调用 CLI、复用 `scalim` 内部逻辑”的约束。
- `yaml-dsl-vscode-extension`: 定义 VSCode 侧与 `redhat.vscode-yaml` 协同的扩展行为（schema 绑定、配置同步、Python venv 管理与 server lifecycle）。

### Modified Capabilities
- （空）

## Impact

- 影响范围（规范层面）：
  - 本仓库：需要保证 `src/scalim/dsl/by_yaml/**` 的关键语义能力可被外部 LSP server 以 library 方式复用（不依赖 CLI 输出格式）。
  - schema 产出：LSP/扩展需要稳定获取 `demand.gen.json` / `workflow.gen.json`（可通过资源读取或发布包携带）。
- 兼容性与边界：
  - `src/scalim/` 运行时边界仍需兼容 Python 3.6；LSP server 运行时版本由 `pygls` 决定（建议 `>=3.9`，在独立仓库约束）。
  - 本提案不再考虑仓库内 Web 编辑器；编辑体验以 LSP/IDE 集成为主。

## Calibration Notes (2026-03-25)

- YAML DSL 自本提案创建以来已经历大量迭代,新增能力包括:
  - `yaml-dsl-imports`（`$import` 展开）
  - `yaml-dsl-workflow-validate`（workflow validate CLI）
  - `yaml-template-vars-precompile` / `yaml-template-vars-sandbox`
  - `yaml-dsl-micro-tunes`（语法减痛改良）
  - `yaml-dsl-import-aliases-and-presets`
  - 以上均已归档并同步到主规范
- LSP server 的 Diagnostics 能力边界需重新校准:demand validator 已包含 imports 展开/unknown fields/legacy fields/template vars 等,workflow 则已有独立的 validate CLI
- `yaml-dsl-extensions` 方向已从 notplan 移除,LSP 设计不再需要考虑 extensions 语义
- `frontend/scalim-yaml-dsl-editor/` Web 编辑器已移除
- 建议: 如启动此提案,优先评估 `scalim.config.yaml` 是否可与 `pyproject.toml` 或 `scalim-cli` 已有的项目发现机制整合,避免引入额外配置文件
