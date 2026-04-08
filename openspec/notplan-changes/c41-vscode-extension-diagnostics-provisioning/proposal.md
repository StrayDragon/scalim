## Why

VSCode 扩展（`extras/vscode-scalim/`）是用户接触 YAML DSL 编辑体验的入口，负责把 schema 校验（`redhat.vscode-yaml`）与语义能力（LSP server）组合起来。当前扩展在"能用"层面基本到位，但用户反馈集中在两类结构性问题：

1. **环境与生命周期不可观测**：安装/升级/启动失败时，用户不知道"它到底用的是哪个 Python、哪个 scalim.yaml、哪个 python_roots"，也无法自助排查。
2. **配置修复缺乏引导**：当 `scalim.yaml` 缺失、roots 不对、imports 越界时，用户只看到编辑器里的波浪线，不知道该改哪个文件、怎么改。

本提案聚焦：**让扩展具备"可观测、可诊断、可引导配置"的能力**，把"首次安装到正常工作"和"出问题后自助排障"这两条路径做到一键可用。

补充现状（对齐当前代码基线）：扩展已具备 OutputChannel、Status Bar、基础 provisioning（pinned venv/workspace venv/PATH）、以及 discovery dump / 打开或创建 `scalim.yaml` 的入口。本文档后续内容更偏向“把缺口补齐并固化为可复用 UX”，而不是从零开始。

## Principles

- 语义 SSOT 在 server / shared core；extension **不复制** YAML DSL 规则，只做 orchestration 与 UX。
- 默认安全：不执行用户代码，不静默改写 workspace，不在失败时污染非 DSL YAML 体验。
- 所有"改配置"的动作都必须用户确认后才应用（WorkspaceEdit / 明确提示弹窗）。

## Goals

- **G1：日志与诊断可一键获取**：用户能通过命令/状态栏快速查看 server 状态、discovery 结果、最近错误。
- **G2：Status Bar 外显状态**：server 运行状态、discovery 结果一目了然，不需要"猜"。
- **G3：Doctor 预检**：一键跑完常见 preflight 检查，输出可复制的诊断报告。
- **G4：Setup Wizard 引导**：首次安装或环境变更时，通过向导完成 server provisioning 与 workspace 配置。
- **G5：scalim.yaml 生命周期管理**：快速定位/打开/创建 `scalim.yaml`，变更时自动感知。

## Non-Goals

- 不引入新的语义 UI（Tree View / Virtual Documents 由 c44 负责）。
- 不在 extension 侧复制 LSP 语义规则。
- 不做 workspace-wide 全量索引或扫描。

## Proposal

### 1) 统一日志与诊断入口

#### Commands

| 命令 | 行为 |
|---|---|
| `Scalim: Open Logs` | 打开 OutputChannel `Scalim YAML DSL`（分级：INFO/WARN/ERROR） |
| `Scalim: Open Server Log File` | 打开 globalStorage 下的 server log 文件（原始日志，比 OutputChannel 更完整） |
| `Scalim: Copy Diagnostic Bundle` | 一键复制可粘贴到 issue 的文本到剪贴板 |

#### Diagnostic Bundle 内容

不包含 YAML 正文（隐私），至少包括：

- extension 版本、server 包版本
- Python 可执行路径与 `python --version` 输出
- Discovery 摘要：
  - project_root
  - scalim.yaml 路径（找到 / 未找到）
  - python_roots 列表
  - allowed_yaml_roots 列表
  - import_aliases 列表
- 最近一次 resolution trace（来自 c40 的 ResolutionTrace，若 server 支持）
- Server 状态（Running / Stopped / Error）

### 2) Status Bar

#### 显示内容

一个 Status Bar Item，显示两部分信息：

- **Server 状态**：`$(check) Scalim` / `$(sync~spin) Scalim` / `$(x) Scalim` / `$(error) Scalim`
  - Running / Starting / Stopped / Error
- **Discovery 状态**（tooltip 或第二段文字）：
  - 找到 `scalim.yaml`：显示 project_root 名
  - 未找到：显示 `No scalim.yaml`

#### 交互

- 单击：打开 Quick Pick，选项包括：
  - Open Logs
  - Show Discovery Summary（在 OutputChannel 打印完整 discovery dump）
  - Restart Server
  - Run Doctor
- 状态变化时自动刷新（server start/stop/discovery complete）。

### 3) Doctor（预检命令）

#### 命令

`Scalim: Doctor`

#### 检查项

按顺序执行，全部通过显示"All checks passed"，否则显示第一个失败项 + 修复建议：

1. **Python 版本**：`python --version` >= 3.10？
   - 失败 → 显示"需要 Python 3.10+，当前为 X.Y"，给出安装/切换指引。
2. **Server 包安装**：`scalim-yaml-dsl-lsp` 是否安装？版本是否与 extension pinned 匹配？
   - 未安装 → 建议运行 Setup Wizard 或 `pip install`。
   - 版本不匹配 → 显示"期望 X.Y.Z，当前为 A.B.C"。
3. **scalim.yaml 存在**：workspace 中是否存在 `scalim.yaml`？
   - 不存在 → 提供"创建 scalim.yaml"按钮（从模板）。
   - 存在但不在 workspace root → 提示路径。
4. **yaml.schemas 绑定**：VSCode settings 中 `yaml.schemas` 是否已正确绑定 DSL schema？
   - 未绑定 → 提供"自动绑定"按钮（修改 workspace settings，需用户确认）。
5. **Server 启动**：LSP server 是否正在运行？
   - 未运行 → 提供"Restart Server"按钮。

#### 输出

在 OutputChannel 显示完整报告，同时弹出一个可复制的信息面板（不含 YAML 正文）。

### 4) Setup Wizard（引导式配置）

#### 触发方式

- 命令面板：`Scalim: Setup Wizard`
- 首次启动时自动提示（可关闭"不再提示"）

#### 步骤

**Step 1：选择 Server Provisioning 模式**

| 模式 | 说明 | 适用场景 |
|---|---|---|
| Extension venv（默认） | 在 extension globalStorage 下创建 venv 并安装 server | 大多数用户 |
| Workspace venv | 复用 workspace 的 Python 环境 | 需要与项目依赖一致的高级用户 |
| PATH | 使用 PATH 中的 `scalim-yaml-dsl-lsp` | CI / 特殊环境 |

**Step 2：版本选择**

- 显示 pinned 默认版本（extension 建议版本）。
- 允许用户覆盖为其他版本（输入框，非必填）。

**Step 3：确认并应用**

- 显示将要执行的操作摘要（例如"将在 ~/.vscode/extensions/.../globalStorage 创建 venv 并安装 scalim-yaml-dsl-lsp==X.Y.Z"）。
- 用户确认后执行。
- 安装完成后自动 restart server。

#### 护栏

- 所有文件系统写操作都在确认后执行。
- 安装失败时显示完整错误信息 + 回退选项。
- 不修改 workspace 的 `.gitignore` / `requirements.txt` 等文件。

### 5) scalim.yaml 生命周期管理

#### Commands

| 命令 | 行为 |
|---|---|
| `Scalim: Open scalim.yaml` | 打开 nearest `scalim.yaml`（向上搜索 workspace）；不存在则弹出"创建？"确认框 |

#### 文件监听

- 监听 `**/scalim.yaml` 的 create / change / delete 事件。
- 变更时：
  - 更新 Status Bar 的 discovery 状态。
  - 弹出 notification："scalim.yaml 已变更，是否重启 LSP server？"（可配置为自动重启）。
- 删除时：
  - 更新 Status Bar 为"No scalim.yaml"。
  - 不自动重建（需用户显式操作）。

## Options & Trade-offs

### 1) Extension venv vs Workspace venv

- **Extension venv（推荐默认）**：隔离、稳定、不被用户环境干扰；安装一次成本。
- **Workspace venv**：与项目依赖一致；但更容易被用户弄坏（pip install 冲突、版本漂移），解释成本高。
- Setup Wizard 让用户自选，默认推荐 extension venv。

### 2) 自动修复 vs 显式确认

- 对 `scalim.yaml` / workspace settings 的改写：**必须用户确认**（推荐）。
- 对纯只读行为（日志、诊断包、discovery dump）：**可以自动**。

### 3) Doctor 检查项的扩展性

- 当前 5 项覆盖最常见的 failure mode。
- 后续可新增检查项（例如"c42 的 builtin 词表是否可加载"），但不应在首次迭代做太多。
- 建议用简单的 check list 模式，每项独立、可单独跳过。

## Validation

- **手动冒烟**：
  - 全新 workspace（无 scalim.yaml、无 venv）→ Setup Wizard 指导完成安装 → Doctor 全绿 → Status Bar 显示 Running。
  - 故意制造错误（删 scalim.yaml、改坏 roots）→ Status Bar 变红 → Doctor 显示具体失败项 → Quick Fix 可修复。
  - "Copy Diagnostic Bundle" → 粘贴到文本编辑器 → 内容完整且不含 YAML 正文。
- **自动化**（最小）：
  - extension e2e：启动扩展 → server up → 命令可用（Open Logs / Doctor / Status Bar 可见）。

## Impact（涉及模块）

- VSCode 扩展源码：`extras/vscode-scalim/`
  - 新增 commands（Doctor / Setup Wizard / Copy Diagnostic Bundle / Open scalim.yaml）
  - Status Bar Item
  - File Watcher for `scalim.yaml`
  - OutputChannel 日志整合
- 可能涉及 server 侧：
  - 如果 server 尚未暴露 discovery 状态，需要新增一个 `workspace/executeCommand` 或 custom notification。
- specs（后续转正时）：
  - `openspec/specs/yaml-dsl-vscode-extension/spec.md`
  - `openspec/specs/yaml-dsl-lsp-editor-integration-guides/spec.md`
