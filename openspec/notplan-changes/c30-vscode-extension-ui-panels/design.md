## Context

- `vscode-extension-diagnostics-provisioning` 提供了“可观测/可诊断/可引导配置”的基础入口（日志、Status Bar、Doctor、Setup Wizard）。
- 日常 authoring 仍缺少“可视化理解与浏览”能力:
  - 文件结构大纲（sources/fields/relations/outputs/workflow）
  - effective YAML 与解析链路的只读预览
  - Quick Fix 的集中浏览入口（而不是依赖灯泡触发）
- server 侧已有/将新增的可复用数据源:
  - YAML language server 的通用 `textDocument/documentSymbol`（可通过 VSCode 的 `vscode.executeDocumentSymbolProvider` 获取）
  - `ResolutionTrace`（来自 `yaml-dsl-lsp-resolution-infra`）
  - effective expansion（来自 `yaml-dsl-editor-effective-expansion`）
  - preset text（来自 `yaml-dsl-lsp-sugar-support`）

约束/护栏:
- 语义数据来自 LSP server；extension 只做渲染与交互编排。
- 所有 UI 面板只读；不在 UI 中直接编辑 DSL。
- 非 DSL YAML 不打扰（不显示 explorer/状态提示，或显示“Not applicable”）。

## Goals / Non-Goals

**Goals:**
- Tree View（DSL Explorer）：展示当前文件的实体层级并可点击跳转。
- Virtual Documents/Preview：只读预览 effective YAML、resolved reference、preset 内容。
- Quick Fix 浏览面板：列出当前文件所有可用 Quick Fix 并可执行。
- DSL 类型指示：显示 demand/workflow + schema 绑定状态，并提供 Explain 命令。

**Non-Goals:**
- 不在 extension 侧解析 DSL 语义（不复制规则）。
- 不做 webview（优先用只读 editor tab + TreeView）。
- 不做 rename/refactor UI。

## Decisions

### 1) Tree View: 首选复用通用 `documentSymbol`

- extension 实现 `TreeDataProvider`:
  - 监听 active editor 变化
  - 通过 VSCode 内建命令 `vscode.executeDocumentSymbolProvider` 获取 symbols（由 YAML language server 提供）
  - 将 `DocumentSymbol` 映射为 TreeItem（label/icon/tooltip）
  - 点击 TreeItem 调用 `revealRange` 跳转到对应位置
- 若 symbol 信息不足以展示更多细节（loader、steps 数量等），再引入 server command（例如 `scalim.getDocumentStructure`）作为增量扩展，而不是一开始就自定义协议。

### 2) Virtual Documents: 统一 provider + 多 route

- extension 只注册一个 `TextDocumentContentProvider`，支持多个 scheme:
  - `scalim-effective://<file>` → effective YAML（imports/$import 展开 + 来源注释）
  - `scalim-resolved-ref://<file>#<pos>` → resolved reference（归一化路径 + trace 摘要 + locations）
  - `scalim-preset://<id>` → preset YAML（只读）
- 内容获取统一走 `workspace/executeCommand`：
  - provider 收到 URI → 解析 route → 调用对应 server command 拉取 `content`
  - 返回 `content` 给 VSCode 打开只读 tab
- 与其它变更的 virtual docs 共享同一套 scheme/provider/路由，避免维护成本膨胀。

### 3) Quick Fix 浏览: 标准 `textDocument/codeAction` + Quick Pick

- 命令 `Scalim: Show Available Quick Fixes`:
  - 对当前文档请求 `textDocument/codeAction`（可用全量 diagnostics 或当前 selection range）
  - 将返回的 actions 映射到 Quick Pick items（标题 + 诊断摘要 + 来源）
  - 选择后执行:
    - 若包含 `edit` → `workspace.applyEdit`
    - 若包含 `command` → `commands.executeCommand`
- 性能护栏: 仅用户显式触发时请求，不自动轮询。

### 4) DSL 类型指示: 状态最小化 + Explain 命令

- 状态展示位置:
  - status bar 的第二段或 editor 顶部轻量提示（不强制）
- 判定来源:
  - 优先来自 server discovery（必要时可用 documentSymbol 非空作为弱信号）
  - schema 绑定状态通过读取 `yaml.schemas` 配置判断（workspace settings）
- 命令 `Scalim: Explain DSL Status`:
  - 输出“为何未激活/已激活”的解释（用于排障，避免常态噪声）

### 5) 文档/生成边界与 drift gates（必须）

- 手工编辑范围:
  - `extras/vscode-scalim/src/**`
  - （如需补 server command）`packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/**`
- 禁止手改:
  - `extras/vscode-scalim/dist/**`、`extras/vscode-scalim/out/**`
  - 任意 `*.gen.*` 与 `BEGIN/END AUTOGEN:*` 区块内部
- Drift gates:
  - repo: `just qa`、`just openspec-check`
  - extension: `pnpm -C extras/vscode-scalim lint`、`pnpm -C extras/vscode-scalim test`

## Risks / Trade-offs

- [TreeView 依赖 documentSymbol 质量] → 先用 documentSymbol 作为最小实现；信息不足再加 server command，避免过早自定义协议。
- [virtual docs 与 server 命令耦合] → 统一 content 协议（`{content,title,languageId}`），并在 extension 侧集中路由，减少散点依赖。
- [Quick Fix 执行副作用] → 只执行 server 提供的 workspace-scoped edit/command；执行前在 UI 提示变更范围（如有必要）。
