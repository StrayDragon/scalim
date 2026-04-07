## Why

YAML DSL 的“编辑体验”最终落在 VSCode 扩展上：它负责把 schema（`redhat.vscode-yaml`）与语义（LSP server）组合成一个可用、可排障、可升级的整体。

用户反馈通常集中在两类问题：

1) **环境与生命周期**（安装/升级/启动失败、Python 版本不对、多个工作区/多 root 复杂）  
2) **可观测与排障**（“现在它到底用的是哪个 scalim.yaml / python_roots / allowed_roots？”“为什么跳转失败？”）

因此需要一份 VSCode extension roadmap：在不复制 server 语义的前提下，把 provisioning、诊断输出、交互入口与 UI 体验补齐。

## Principles（扩展侧护栏）

- 语义 SSOT 在 server/shared core；extension **不复制** YAML DSL 规则，只做 orchestration 与 UX。
- 默认安全：不执行用户代码，不静默改写 workspace，不在失败时污染非 DSL YAML 体验。
- 所有“改配置”的动作都必须可撤销、可审计（WorkspaceEdit / 明确提示）。

## Roadmap（分阶段）

### Phase 0：把“可排障”做到一键可用（高优先级）

1) 统一日志与诊断入口
- OutputChannel：`Scalim YAML DSL`（分级：INFO/WARN/ERROR）
- “打开 server 日志文件”命令（定位到 globalStorage 的 log）
- “复制诊断包”命令：一键复制可粘贴到 issue 的文本（不包含 YAML 正文），至少包括：
  - extension 版本、server 版本
  - Python 可执行路径与版本
  - discovery 摘要（project_root / scalim.yaml 路径 / python_roots / allowed_yaml_roots / import_aliases）
  - 最近一次解析失败的 warning trace（若有）

2) Status Bar：把状态外显（避免“到底有没有在工作？”）
- server 状态：Running / Starting / Stopped / Error
- discovery 状态：找到/未找到 `scalim.yaml`、当前 project_root
- 点击打开：日志 / discovery dump / 重启 server

3) “医生模式”（Doctor）
- 一个命令跑完最常见的 preflight：
  - Python >=3.10？（不满足给出清晰指引）
  - server 包是否安装/版本是否匹配 pinned？
  - workspace 中是否存在 scalim.yaml？最近的是哪个？
  - yaml.schemas 是否已正确绑定（与 `redhat.vscode-yaml` 协作）
- 输出一份可复制的报告（同样不包含 YAML 正文）

### Phase 1：把“配置与修复”变成引导式体验（减少上手成本）

1) Setup Wizard（可选、显式触发）
- 选择 server provisioning 模式：
  - 使用扩展 venv（默认）
  - 使用 workspace venv（高级用户）
  - 使用 PATH 中的 `scalim-yaml-dsl-lsp`（仅当可诊断且用户确认）
- 选择 pinned 版本（默认建议，允许覆盖）
- 自动写入/更新必要的 workspace settings（用户确认后应用）

2) Quick Fix 的可视化升级
- server 返回的 code actions 在编辑器里是灯泡，但用户不知道“还有哪些修复命令”。
- extension 侧提供一个面板/命令：列出“当前文件可用的 Quick Fix”，并可一键执行（仍然由 server 提供 edit/command）。

3) scalim.yaml 管理
- 命令：打开 nearest `scalim.yaml`（没有则提供创建）
- 文件监听：`scalim.yaml` 变更后提示用户重载/自动重启 server（可配置）

### Phase 2：VSCode 特有 UI（提升日常使用效率）

1) YAML DSL Explorer（Tree View）
- 当前文档结构树：sources / fields / relations / outputs
- 点击节点跳转到定义
- 可显示计数/错误标记（来自 diagnostics，而非自行解析语义）

2) Virtual Documents / Preview（只读）
- “Effective YAML”（imports 展开后的最终 YAML，带来源 trace）
- “Resolved Python Reference”（显示 reference 归一化后的 module path + 解析链路）
- “Schema Quick Reference”（链接到仓内文档/生成页）

3) UX 小增强
- 在 YAML 顶部显示“这是什么 DSL（demand/workflow）”与 schema 状态
- 当文件被判定为非 DSL YAML 时，提供 explain（为何不激活）而不是默默不工作

## Trigger Forms（用户触发方式）

- 自动触发：打开/编辑 YAML 文件（按 DSL 探测激活）
- 命令面板：
  - `Scalim: Restart LSP`
  - `Scalim: Show Discovery Summary`
  - `Scalim: Open Logs`
  - `Scalim: Doctor`
  - `Scalim: Setup Wizard`
- 编辑器内：
  - Quick Fix（灯泡）
  - 状态栏点击
  - Tree View 点击

## Options & Trade-offs

1) 扩展 venv vs workspace venv
- 扩展 venv（推荐默认）：隔离、稳定、可控；缺点是需要一次安装成本。
- workspace venv：与项目依赖一致；缺点是更容易被用户环境弄坏（解释成本高）。

2) 自动修复 vs 显式确认
- 对 `scalim.yaml` / settings 的改写必须用户确认（推荐），否则容易引发信任问题。
- 对纯只读行为（日志/诊断包）可以自动。

3) Tree View / Preview 的语义来源
- 推荐：所有语义数据来自 LSP server 的标准能力或扩展命令（SSOT）。
- 不推荐：extension 自己解析 YAML 并推断（重复实现、容易漂移）。

## Validation（验收口径）

- 手动冒烟：
  - “全新 workspace”首次安装 → wizard/doctor 能指导成功启动
  - 故意制造错误（缺 scalim.yaml、roots 不对）→ 能一键看到原因 + Quick Fix
- 自动化：
  - 尽量用现有 extension e2e 框架（如有）做最小集成测试：启动扩展 → server up → 命令可用

## Impact（涉及模块）

- VSCode 扩展源码：`extras/vscode-scalim/`
- 规范演进（后续转正时）：
  - `openspec/specs/yaml-dsl-vscode-extension/spec.md`
  - `openspec/specs/yaml-dsl-lsp-editor-integration-guides/spec.md`
