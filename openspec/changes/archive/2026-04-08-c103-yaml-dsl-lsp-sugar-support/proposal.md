## Why

YAML DSL 在运行时已经支持一些关键语法糖（`^<id>` builtin callable、imports 路径别名、`scalim://...` preset），用于提升复用性并收紧 allowlist/allowed-roots 的安全边界。但编辑器侧（LSP/VSCode）目前缺少与之对齐的 completion/hover/definition/quick fix，导致“能跑但不好写/不好查/不好排障”的落差，且配置缺失时用户难以自助修复。

本变更聚焦：**让这些语法糖在 LSP/VSCode 中具备同等“可探索性 / 可跳转 / 可修复”**，并保持静态、安全边界不被弱化。

## Goals

- **G1：可探索**：completion/hover 能解释 sugar 的含义与可用值。
- **G2：可跳转**：尽可能提供 definition（打开实现 / 打开 fragment / 打开 preset 内容）。
- **G3：可修复**：当 sugar 因配置缺失而失败时，提供 Quick Fix 指向正确的修复位置（通常是 `scalim.yaml`）。
- **G4：不破坏护栏**：静态无副作用；不执行用户代码；不隐式放宽 imports allowed-roots。

## Non-Goals

- 不把“运行时动态注入 builtin_callables（RunOptions）”完整暴露到编辑器（除非有明确、安全的配置入口）。
- 不在 editor 侧隐式放宽运行时约束（allow-roots/allowlist 仍以运行时校验为准）。
- 不做 YAML DSL 内部实体 ID 导航（由 `yaml-dsl-entity-navigation` 负责）。
- 不做 effective expansion（anchors/aliases/flatten/imports 展开与 outputs.fields 导航由 `yaml-dsl-editor-effective-expansion` 负责）。
- 不实现 Doctor/Setup Wizard（由 `vscode-extension-diagnostics-provisioning` 负责）。

## What Changes

### 1) `^<id>` builtin callable：definition / hover / completion

- completion：在 `^` 后提供可用 builtin ids 列表与摘要（保守词表）。
- hover：展示 id 含义、映射目标与关键约束（静态无副作用）。
- go-to-definition：尽可能定位到 Python 实现或对应的 SSOT 文档位置；失败时提供可诊断的降级信息。

### 2) imports 路径别名（path alias prefix）：`@/x.yaml` 与 `ALIAS:/x.yaml`

说明：这里的 “path alias prefix” 指 `imports.<key>` 的 value 字符串里使用的前缀（`@/`、`COMMON:/` 等）。
该前缀来自 `scalim.yaml` 的 `yaml_dsl.import_roots[*].alias`（SSOT），并与 imports allow-roots 边界绑定。

- completion：补全 alias 前缀与 alias base_dir 下的相对路径（仅 `.yaml/.yml`）。
- hover：解释 alias 匹配、resolved path 与 allowed-roots 校验结论（含可诊断原因）。
- go-to-definition：跳转到目标 fragment 文件（文件级即可）。
- quick fix：当 alias 未配置/越界时，提供指向 `scalim.yaml` 的修复建议（需用户确认后应用 WorkspaceEdit）。

### 3) `scalim://...` preset：可打开/可跳转

- hover：解释 preset id、来源与只读属性。
- go-to-definition：打开只读虚拟文档（推荐）或降级跳转到仓内 SSOT 文件/文档，用于“像文件一样查看 preset 内容”。

### 4) 全程保持静态与安全边界

- 不执行用户代码；不通过 shell-out CLI 推导语义。
- 不隐式放宽 allowlist/allowed-roots；所有修复均需用户确认。
- 失败必须可诊断（trace/降级信息），不得 crash/卡死。

## Proposal（按语法糖拆分）

### 1) `^<id>` builtin callable：definition / hover / completion

#### Reference Forms

- loader：
  - `main_source.loader: ^workflow/book_sheet_rows`
  - `sources.*.loader: ^workflow/book_sheet_rows`
- call_by（忽略参数段定位）：
  - `fields.*.call_by: "^workflow/book_sheet_rows(ref)"`

#### Trigger Forms

- Completion：在 `^` 后触发（Ctrl+Space + 自动提示）
- Hover：悬停在 `^<id>` 上
- Go to Definition：F12

#### Expected Behavior（推荐）

1) Completion
- 列出“框架内置保守词表”中的 builtin ids（例如 `workflow/book_sheet_rows`）
- 显示一行摘要（若有）
- 对 call_by 位置提供 snippet：`^workflow/book_sheet_rows(${1:arg}=${2:value})`

2) Hover
- 展示 builtin id 与摘要（若有）
- 若可映射到 Python 引用：展示解析后的 python ref（仅静态展示，不执行）

3) Go to Definition（多 locations）
- **首选**：跳到 builtin 对应的 Python 实现（若可映射为 python ref 且能静态解析到文件/符号）
- **备选**：跳到 builtin 词表/文档位置（仓内 SSOT 文档或 spec 对应段落）
- **降级**：返回空 + warnings，并给出“可用 id 列表入口”的指引

#### Options & Trade-offs（builtin 词表来源）

Option A（推荐默认）：只支持“框架内置保守词表”
- 维护性：高（SSOT 在 `scalim` 内部；编辑器只读）
- 体验：覆盖多数场景；下游自定义 builtin_callables 不补全/不跳转

Option B：允许在 `scalim.yaml` 声明“editor 扩展词表”
- 体验：更强（下游团队可补全/跳转常用 builtin）
- 风险：需要明确“这不等于运行时允许运行任意模块”，只是可解析的静态词表

### 2) imports 路径别名（path alias prefix）：`@/x.yaml` 与 `ALIAS:/x.yaml`

#### Background

imports 的 value 本质上是相对路径，但通过 `scalim.yaml` 的 `yaml_dsl.import_roots` 可以引入路径别名前缀（path alias prefix）：

- `@/x/y.yaml`（当 alias 以 `@` 开头时使用 `@/` 语法）
- `COMMON:/x/y.yaml`（一般 alias 使用 `ALIAS:/` 语法）

如果 path alias prefix 未配置，运行时/编辑器都必须 fail-fast（安全边界），但 editor 侧应给出更“行动导向”的提示与 Quick Fix。

#### Reference Forms

```yaml
imports:
  common: "@/fragments/common.yaml"
  shared: "COMMON:/fragments/shared.yaml"
```

#### Trigger Forms

- Hover：悬停在 `imports.*` 的 value 字符串上
- Go to Definition：F12（对 imports value）
- Completion：在 value 内输入 `@/` 或 `ALIAS:/` 时触发
- Quick Fix：当解析失败时提供（灯泡）

#### Expected Behavior（推荐）

1) Hover（imports value）
- 展示 raw path、path alias prefix 匹配结果、resolved path、以及 allow-roots 校验结论（通过/失败原因）

2) Go to Definition（imports value）
- 直接跳到 fragment 文件本身（文件起始即可）

3) Completion（imports value）
- 在开头补全：
  - `./`、`../`、`<dir>/...`（相对路径）
  - 已配置的 path alias prefixes（例如 `@/`、`COMMON:/`）
- 在 alias 已确定后，按 alias 对应 base_dir 做相对路径补全（仅 `.yaml/.yml`）

4) Quick Fix（当 path alias prefix 未配置/越界）
- “Add import root `<dir>` (alias=`@`/`COMMON`) to scalim.yaml”
- 必须是 workspace-scoped；所有文件改写需用户确认

### 3) `scalim://...` preset：可打开/可跳转

#### Reference Forms

```yaml
imports:
  common: "scalim://yaml-dsl/presets/common.yaml"
```

#### Expected Behavior（推荐）

1) Hover
- 显示 preset id、来源（只读、本地白名单）与只读属性

2) Go to Definition

Option A：Virtual Document（推荐）
- definition 打开一个只读虚拟 URI（例如 `scalim-preset://yaml-dsl/presets/common.yaml`）
- 内容为 preset YAML 文本（带 “Generated, read-only” 提示）

Option B：跳到仓内 SSOT 文档/源文件
- 若 preset 对应仓内真实文件或 docs 页，definition 直接打开它

### 4) 关于 `^<scalim:...>`（命名空间写法的建议）

现状：builtin callable id 语法（`^<id>`）默认不支持 `:`。

建议路径：

1) **不改语法（推荐）**：使用前缀分段模拟命名空间
   - 例如：`^scalim/workflow/book_sheet_rows`
2) **扩展语法（可选）**：允许 `:` 作为命名空间分隔
   - 例如：`^scalim:workflow/book_sheet_rows`
   - 需要同步更新 `reference_syntax.py`、schema pattern、文档与 LSP 解析，并明确与 `module:attr` 的 `:` 不冲突（builtin 总以 `^` 开头）

## Validation（fixture 覆盖建议）

- `^<id>`：
  - loader/call_by 两类位置；
  - completion 列表稳定排序；
  - definition 返回（python impl + 文档备选）；
  - unknown id 的诊断与提示。
- imports path alias prefix：
  - `@/` 与 `ALIAS:/` 两种 token；
  - alias 未配置 / 配置但越界 / 文件不存在；
  - hover 的 resolved path 与 allow-roots trace。
- preset：
  - hover explain；
  - definition 打开虚拟文档或 SSOT 文件。

## Capabilities

### New Capabilities

<!-- 本变更优先通过修改既有 LSP/extension/spec 能力实现；不新增 capability spec。 -->

### Modified Capabilities

- `yaml-dsl-editor-semantics-core`: 扩展 shared core 的解析能力，使其可静态解析 `^<id>` / imports path alias prefix / `scalim://...` preset，并产出可诊断的降级信息。
- `yaml-dsl-lsp-server`: 在 definition/hover/completion 上支持上述语法糖，并保证对非 DSL YAML 不污染。
- `yaml-dsl-lsp-code-actions`: 新增/扩展 Quick Fix，使配置缺失（alias/roots 等）可一键引导修复且 workspace-scoped。
- `yaml-dsl-vscode-extension`: 支持打开只读 virtual document（用于 preset 预览），并在 UI 上提供与 Quick Fix/日志的协作入口（不新增 provisioning/doctor 逻辑）。

## Impact

- shared core：`packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/core.py`
  - sugar 引用解析、hover/definition/completion 的统一入口与降级信息
- LSP server：`packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/server.py`
  - handler 覆盖面扩展（definition/hover/completion/codeAction）
  - 与 codeAction/executeCommand 的协议扩展（如需要）
- VSCode extension：`extras/vscode-scalim/`
  - virtual document scheme/provider（preset 预览）
  - 与 server quick fixes 的 UX 集成（仅 orchestration，不复制语义规则）

## Dependencies

- 依赖 `yaml-dsl-lsp-resolution-infra`：multi-location 排序、Resolution Trace、Quick Fix 框架。
- 依赖 `vscode-extension-diagnostics-provisioning`：复用现有日志/状态栏/诊断入口（但不在本变更实现 Doctor/Wizard）。
