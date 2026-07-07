## ADDED Requirements

### Requirement: VSCode MUST provide a sidebar WebviewView "可视化透镜" (Workflow / Demand)
系统 MUST 在 `extras/vscode-scalim` 提供一个侧边栏常驻的 WebviewView，用于在编辑 YAML DSL 时显示轻量关系透镜：

- 透镜 MUST 随 active 文档切换上下文（至少覆盖 workflow 与 demand 两类 YAML）。
- UI 主动作 MUST 命名为 **“生成”**，且未点击“生成”前不得触发静态编译/图生成（零成本默认）。

#### Scenario: open sidebar lens without triggering computation
- **WHEN** 用户打开侧边栏 “可视化透镜”
- **THEN** webview MUST 仅展示空态说明与“生成”按钮
- **AND** 系统 MUST NOT 在后台静态编译 demand/workflow 或生成 Mermaid

### Requirement: Lens MUST be disabled in untrusted workspace
系统 MUST 遵守 VSCode Trusted Workspace 语义：

- 当 `vscode.workspace.isTrusted=false` 时，透镜 MUST 禁用任何来自 workspace 的透镜数据生成与展示。
- webview MUST 展示清晰可读的提示，引导用户信任工作区后再使用。

#### Scenario: untrusted workspace shows guidance only
- **GIVEN** 当前工作区为 untrusted
- **WHEN** 用户打开侧边栏透镜
- **THEN** webview MUST 显示 “需要信任工作区” 的提示
- **AND** 点击“生成” MUST 不产生任何来自 workspace 的透镜数据

### Requirement: Workflow lens MUST provide navigation to runs[*].demand (user-triggered)
系统 MUST 在 active 文档为 workflow YAML 时提供“导航式透镜”，用于从 `workflow.runs[*].demand` 快速跳转到目标 demand（用户触发，不做关系图生成）。

- 用户点击“生成”后，系统 MUST 解析 `workflow.runs[*].demand` 形成候选列表（仅导航，不生成 demand 的关系图）。
- 候选列表项 MUST 提供：
  - “打开”（打开对应 demand 文件）
  - “打开并生成”（打开 demand 文件，并触发 demand 透镜生成）

#### Scenario: workflow generate shows demand candidates
- **WHEN** active 文档为 workflow YAML 且用户点击“生成”
- **THEN** 侧边栏 MUST 展示 `runs[*].demand` 候选列表
- **AND** 不得生成 plan/deps 或 Mermaid

#### Scenario: open-and-generate switches to demand lens
- **GIVEN** workflow 候选列表中存在某 demand 项
- **WHEN** 用户点击 “打开并生成”
- **THEN** 系统 MUST 打开该 demand 文档
- **AND** 侧边栏 MUST 对该 demand 文档生成透镜数据

### Requirement: Demand lens MUST render outputs list + Mermaid local relationship (user-triggered)
系统 MUST 在 active 文档为 demand YAML 时提供“输出锚点 + Mermaid 局部关系”的透镜视图（用户触发，零成本默认）。

- 用户点击“生成”后，系统 MUST 生成透镜数据并渲染：
  - outputs 列表（至少包含 `outputs[*].name`）
  - Mermaid 局部关系图（围绕当前 focus 的 output）
- 透镜数据生成 MUST 通过 LSP `workspace/executeCommand` 调用 `scalim.dumpDemandLens` 获取（扩展侧只负责渲染与交互，避免实现漂移）
- outputs 列表交互 MUST 满足：
  - 单击输出行仅切换 focus（更新 Mermaid），不得自动跳转到编辑器。
  - 每行 MUST 提供“定位”按钮；点击后 MUST 跳转到该 output 的声明位置（`outputs[*].name`）。
- Mermaid 文本源 MUST 默认隐藏，但 MUST 提供“复制 Mermaid”能力。

#### Scenario: generate creates a focused demand lens
- **WHEN** active 文档为 demand YAML 且用户点击“生成”
- **THEN** 侧边栏 MUST 展示 outputs 列表与 Mermaid 关系图

#### Scenario: clicking output only changes focus
- **GIVEN** 透镜已生成且 outputs 列表非空
- **WHEN** 用户单击某个输出行
- **THEN** 侧边栏 MUST 仅更新 focus 与 Mermaid 关系图
- **AND** 编辑器光标位置 MUST 不发生跳转

#### Scenario: locate button reveals output declaration
- **GIVEN** 透镜已生成且 outputs 列表非空
- **WHEN** 用户点击某输出的“定位”
- **THEN** 编辑器 MUST reveal 到该输出的 `outputs[*].name` 声明范围

### Requirement: Mermaid nodes MUST support click-to-jump to field definitions
Demand 透镜中的 Mermaid 图节点 MUST 支持点击跳转：

- 点击字段节点后，系统 MUST 跳转到该字段的定义处（源字段/派生字段），而不是 outputs 引用处。
- 当无法定位定义（例如缺失位置信息）时，系统 MUST 给出可读降级提示且不得 crash。

#### Scenario: clicking a mermaid node reveals a field definition
- **GIVEN** Mermaid 图中存在某字段节点且其定义位置可解析
- **WHEN** 用户点击该节点
- **THEN** 系统 MUST reveal 到该字段定义的位置范围

### Requirement: Webview MUST use strict CSP and postMessage as the only data channel
系统 MUST 使用严格 CSP 的 webview，并满足：

- webview MUST NOT 从远程加载任何资源（JS/CSS/图片）。
- 透镜数据 MUST 仅由扩展侧通过 `postMessage` 注入。
- webview 内脚本 MUST 仅加载 `asWebviewUri` 形式的本地资源。

#### Scenario: lens payload arrives via postMessage
- **WHEN** webview 初始化完成
- **THEN** 在收到扩展侧注入 payload 前，webview MUST 仅展示空态/提示
