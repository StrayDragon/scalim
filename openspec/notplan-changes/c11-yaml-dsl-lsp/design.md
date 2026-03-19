## Context

本变更目标是在 VSCode（以及未来其他编辑器）中提供 Scalim YAML DSL 的语义编辑体验（诊断、跳转、补全、hover），同时保持：

- 结构/Schema 体验继续由 `redhat.vscode-yaml` 提供（不替换、不冲突）。
- LSP server **不调用** `scalim-cli`，仅复用 `scalim` 包内部逻辑与 schema 资源。
- 产物实现放在独立仓库（例如 `scalim-yaml-dsl-lsp`），便于发布/升级；本仓库主要提供可复用的 library 逻辑与可分发的 schema 产物。

约束：

- `src/scalim/` 运行时仍需兼容 Python 3.6（开发工具链可以更高）。
- 文档治理：任何 `.gen.*` 与 `BEGIN/END AUTOGEN:*` 块禁止手改；通过 `just gen-docs` / `just gen` 刷新生成物。
- OpenSpec 变更在共享前必须通过 `just openspec-check` 与 `just qa` 的漂移门禁。

## Goals / Non-Goals

**Goals:**

- 定义 `scalim.config.yaml` 的 v1 结构与默认行为（用于跨编辑器识别 DSL 文件与 python roots）。
- 定义 LSP server v1 的语义边界（Diagnostics/Definition/Completion/Hover），并明确与 schema-only 能力的分工。
- 定义 VSCode 扩展 v1 的协同方式（schema 绑定、配置同步、server lifecycle、Python 环境管理）。
- 收敛本仓库与外部仓库之间的“生成物/SSOT”边界，避免 drift（尤其是 schema 文件）。

**Non-Goals:**

- 不在本仓库实现 VSCode 扩展或 LSP server 的完整工程（仅提供规范与必要的可复用能力）。
- 不改变 YAML DSL 的语义规则与运行时执行逻辑（LSP 仅消费/复用既有逻辑）。
- 不替换 `redhat.vscode-yaml`，不在 v1 中尝试接管 YAML 的 schema 校验/补全。

## Decisions

### 1) LSP server 选型：Python + `pygls`

选择 Python 实现 LSP server：

- 最大化复用 `src/scalim/dsl/by_yaml/**` 的解析/校验/定位能力，避免在 TS 侧复刻并承担对齐成本。
- LSP server 的 Python 版本以 `pygls` 要求为准（建议在独立仓库中固定为 `>=3.9`），不影响本仓库运行时边界（Python 3.6）。

### 2) 配置 SSOT：`scalim.config.yaml`

使用 `scalim.config.yaml` 作为跨编辑器 SSOT：

- 文件识别：以 glob 列表区分 `demand` 与 `workflow`。
- Python roots：供 `loader`/`call_by` 的静态模块落盘定位（不 import 执行）。
- LSP 行为开关：例如诊断触发策略（on_save/on_change debounce）。

当配置文件不存在时，扩展提供默认 glob 与 roots 推导规则，做到“零配置可用”。

### 3) Diagnostics 边界：demand 语义校验 + workflow schema-only（v1）

- demand：复用内部 validator（包含 `$import` 展开、unknown fields、legacy fields 等）并通过 location index 做 line/column 定位映射。
- workflow：v1 仅做 schema-only 校验（读取 `workflow.gen.json`），与当前系统边界对齐，降低首版复杂度。

### 4) 引用字段能力：只在 `loader` / `call_by` 等特定字段生效

为避免 provider 冲突与误触发，Definition/Completion/Hover 只在 YAML 中少量 key 的 string value 范围内生效：

- `loader: "<python reference>"`
- `call_by: "<python reference>(...)"`（取 `parse_call_by(...).reference`）

### 5) 符号定位策略：静态文件系统 + `ast`（不执行代码）

- module -> file：基于 `python.roots` 做落盘解析（`<root>/<module>.py` 或 `<root>/<module>/__init__.py`）。
- symbol 定位：`ast.parse` 找 top-level `def`/`class`，以及 class body 内的 method。
- 相对引用：以 YAML 文件目录为基准处理前导 `.`/`..`，再做同样的落盘解析。

### 6) VSCode schema 绑定：`yamlValidation`（零配置）+ 可选同步到 `yaml.schemas`

并行支持两种机制：

- 零配置：扩展 `package.json` 贡献 `yamlValidation` 默认 glob -> schema（扩展内置 schema 文件）。
- 可配置：当用户自定义 `scalim.config.yaml` globs 时，提供命令把映射写入工作区 `yaml.schemas`（显式可见、可迁移）。

### 7) 生成物与 drift gates

本仓库 SSOT：

- 语义校验逻辑：`src/scalim/dsl/by_yaml/**`
- schema 生成入口：`scripts/gen-yaml-dsl-schema.py` 与 `scripts/gen-yaml-dsl-editor-schema.py`（由 `just gen`/`just qa` 兜底一致性检查）
- OpenSpec 工件：`openspec/changes/c11-yaml-dsl-lsp/**`

外部扩展仓库 SHOULD：

- 通过脚本/CI 从 `scalim` 发布包或指定 tag 拉取 schema（具体来源由外部仓库决定）
- pinned 依赖 `scalim` 与 LSP server 包版本，避免 schema 与语义实现漂移

## Risks / Trade-offs

- [版本漂移（schema/语义）] → 通过 pinned 版本 + schema sync 脚本 + 本仓库 `just qa` 的生成物一致性门禁降低风险。
- [性能：workspace 索引开销] → 采用缓存与增量更新；Completion/Definition 仅在少量字段内触发。
- [安全：引用解析执行代码] → 全部使用静态文件解析（filesystem + `ast`），禁止 import 执行与动态求值。
- [与 YAML 扩展冲突] → 明确分工（schema 能力归 YAML 扩展；LSP 仅做引用字符串与语义诊断），并限制触发点。

## Migration Plan

- M1：schema 自动绑定 + Diagnostics + Definition + Completion + Hover 打通（独立仓库实现）。
- M2：Find References（workspace 扫描引用字符串）+ allowlist 提示（仅提示，不改安全策略）。
- M3：Rename（默认关闭；仅对引用字符串做文本替换，带预览）。

本仓库内：

- 不要求立刻移除 `frontend/scalim-yaml-dsl-editor/`；但后续若将“开发者写配置”主路径迁移至 VSCode 插件，需要另起变更管理收敛与退场计划。

## Open Questions

- `scalim.config.yaml` 是否需要支持多 workspace / 多 root 的覆盖与合并策略？
- workflow 的语义诊断是否需要在 v2 引入完整解析（非 schema-only），其边界与现有 workflow runtime 的契约如何对齐？
- Completion 的包索引是否需要引入文件变更监听（FS watch）以避免全量扫描？

