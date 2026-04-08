## Context

- 代码基线: `extras/vscode-scalim/src/extension.ts` 已具备:
  - OutputChannel（`Scalim YAML DSL`）
  - Status Bar（显示 running/starting/stopped、projectRoot、envKind 等）
  - 基础 provisioning（pinned venv / workspace venv / PATH 的自动选择逻辑雏形）
  - discovery dump / open-or-create `scalim.yaml` 等命令入口
- LSP server 已暴露若干 `workspace/executeCommand`:
  - `scalim.dumpDiscovery`
  - `scalim.yaml.createMinimal`
  - `scalim.yaml.addImportRoots`
  - `scalim.yaml.addPythonRoots`
  - `scalim.python.explainResolutionFailure`

当前缺口集中在两类:
- 可观测性不足：失败时缺少“一键拿全信息”的诊断包与可复制报告。
- 配置引导不足：缺少 Doctor/Setup Wizard 这种“从 0 到可用 / 出问题可自救”的固定 UX。

约束/护栏:
- extension 不复制 YAML DSL 语义规则；语义 SSOT 在 server/shared core。
- 所有会改写 workspace 的动作必须显式确认（WorkspaceEdit / settings 写入 / 文件写入）。
- 诊断输出不包含 YAML 正文（隐私）。

## Goals / Non-Goals

**Goals:**
- 统一日志与诊断入口（OutputChannel + 可打开的 log file + 可复制诊断包）。
- Status Bar 外显状态（server 状态 + discovery 摘要），并提供 Quick Pick 操作菜单。
- Doctor：一键 preflight 检查并给出可执行的修复入口。
- Setup Wizard：首次安装/环境漂移时的引导式 provisioning（用户确认后执行）。
- `scalim.yaml` 生命周期管理：定位/打开/创建 + 文件变更监听 +（可选）提示/自动重启 server。

**Non-Goals:**
- 不引入 Tree View / Virtual Documents 等可视化 UI；本变更只做诊断/引导类 UX。
- 不在 extension 侧做“静态语义推断”（例如 imports 解析、builtin 词表）；仅做 orchestration/UX。
- 不静默改写 workspace（包括 `.gitignore`、`requirements.txt` 等）。

## Decisions

### 1) 日志体系: OutputChannel + 文件落盘

- 继续保留 OutputChannel 作为用户可见日志入口（默认 INFO/WARN/ERROR）。
- 在 `context.globalStorageUri` 下落盘:
  - `extension.log`：extension 自身日志（provisioning/doctor/wizard）
  - `server.log`：server 的原始日志（若 server 支持以文件方式输出；否则由 extension 代理保存“关键事件 + 错误栈”）
- 命令:
  - `Scalim: Open Logs` → `output.show(true)`
  - `Scalim: Open Server Log File` → `openTextDocument(globalStorage/server.log)`

### 2) “诊断包”聚合: `Copy Diagnostic Bundle`

- 在 extension 内实现 `buildDiagnosticBundle()`，输出纯文本（可粘贴到 issue）:
  - extension 版本、server 版本、envKind、pinned spec
  - Python 可执行路径、`python --version` 原始输出
  - discovery 摘要（来自 `scalim.dumpDiscovery`）
  - VSCode `yaml.schemas` 绑定状态（workspace settings）
  - 最近一次启动错误（`lastStartError`）与最后一次重启时间
  - （若 server 支持）最近一次 `ResolutionTrace` 摘要（来自 `yaml-dsl-lsp-resolution-infra`）
- 明确禁止包含:
  - YAML 正文
  - 用户文件内容
- 命令实现:
  - `Copy Diagnostic Bundle` → `vscode.env.clipboard.writeText(bundle)`

### 3) Status Bar UX: “状态 + 菜单”一体化

- Status Bar item 单击不再直接“showDiagnostics”，而是打开 Quick Pick 菜单（稳定入口）:
  - Open Logs
  - Show Discovery Summary
  - Restart Server
  - Run Doctor
  - Setup Wizard
- 显示策略:
  - 文档类型（demand/workflow/config）作为后缀
  - discovery 成功时显示 projectRoot basename；失败显示 `No scalim.yaml`/`<unknown>`

### 4) Doctor: 可复制报告 + 可执行修复入口

- 命令: `Scalim: Doctor`
- 检查项按“最常见失败链路”排序（失败即短路，但仍输出完整报告）:
  1. Python >= 3.10（复用现有 `detectPython`）
  2. server 包安装与版本（与 pinned spec 对齐）
  3. `scalim.yaml` 存在与路径（调用 `scalim.dumpDiscovery`）
  4. `yaml.schemas` 绑定（复用 `internal/yamlSchemas.ts` 的合并写入逻辑，但必须用户确认）
  5. LSP server 运行状态（必要时提供 Restart）
- 输出:
  - OutputChannel 打印全量
  - 最终弹窗提供快捷按钮：`Open Logs` / `Copy Bundle` / `Setup Wizard`

### 5) Setup Wizard: 引导式 provisioning（显式确认后执行）

- 命令: `Scalim: Setup Wizard`
- 交互分步:
  1. 选择 provisioning 模式（pinned venv / workspace venv / PATH）
  2. 版本选择（默认 pinned spec，可选覆盖）
  3. 预览将执行的操作摘要（路径 + pip install spec）
  4. 用户确认后执行；失败时展示完整错误并给回退选项
- 写入边界:
  - pinned venv 仅写 `globalStorage`
  - workspace venv 仅在用户选择后才使用（不自动创建/修改 `.venv`）
  - 不改写 workspace 代码文件

### 6) `scalim.yaml` 生命周期: watcher + 交互式重启

- 注册 `FileSystemWatcher("**/scalim.yaml")`:
  - create/change/delete 时更新 status bar discovery 状态
  - change 时提示“是否重启 LSP server？”（可配置自动重启）
- 继续保留并强化 `Scalim: Open scalim.yaml`:
  - 就近向上搜索；不存在则询问创建（调用 `scalim.yaml.createMinimal`）

### 7) 文档/生成边界与 drift gates（必须）

- 手工编辑范围:
  - `extras/vscode-scalim/src/**`
- 禁止手改:
  - `extras/vscode-scalim/dist/**`、`extras/vscode-scalim/out/**`（构建产物）
  - repo 内任意 `*.gen.*` 与 `BEGIN/END AUTOGEN:*` 区块内部
- Drift gates（建议）:
  - repo: `just qa`、`just openspec-check`
  - extension: `pnpm -C extras/vscode-scalim lint`、`pnpm -C extras/vscode-scalim test`（或其 justfile 封装命令）

## Risks / Trade-offs

- [provisioning 失败率高（网络/权限/代理）] → Setup Wizard 必须输出完整 stderr，并提供切换到 workspace venv / PATH 的回退选项。
- [Doctor 误判/噪声] → 报告结构化输出（每项 PASS/FAIL + 建议动作），避免堆叠不可操作的信息。
- [隐私风险] → bundle 严禁包含 YAML 正文，仅收集路径/版本/摘要；必要时对路径做最小化（basename）展示。
- [跨平台差异（Windows）] → 统一通过 `getVenvScriptsDir`/`findVenvExecutable`，避免硬编码 `bin/`。
