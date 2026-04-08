## Why

YAML DSL 在运行时已经支持一些关键语法糖（`^<id>` builtin callable、imports 路径 alias、`scalim://...` preset），用于提升复用性并收紧 allowlist/allowed-roots 的安全边界。但编辑器侧（LSP/VSCode）目前缺少与之对齐的 completion/hover/definition/quick fix，导致“能跑但不好写/不好查/不好排障”的落差，且配置缺失时用户难以自助修复。

## What Changes

- 为 `^<id>` builtin callable 引用补齐 editor 语义：
  - completion：在 `^` 后提供可用 id 列表与摘要（保守词表）。
  - hover：展示 id 含义、映射目标与关键约束（静态无副作用）。
  - go-to-definition：尽可能定位到 Python 实现或对应的 SSOT 文档位置；失败时提供可诊断的降级信息。
- 为 imports 路径 alias（例如 `@/x.yaml`、`ALIAS:/x.yaml`）补齐 editor 语义：
  - completion：补全 alias 前缀与 alias base_dir 下的相对路径（仅 `.yaml/.yml`）。
  - hover：解释 alias 匹配、resolved path 与 allowed-roots 校验结论（含可诊断原因）。
  - go-to-definition：跳转到目标 fragment 文件（文件级即可）。
  - quick fix：当 alias 未配置/越界时，提供指向 `scalim.yaml` 的修复建议（需用户确认后应用 WorkspaceEdit）。
- 为 `scalim://...` preset 补齐 editor 语义：
  - hover：解释 preset id、来源与只读属性。
  - go-to-definition：打开只读虚拟文档（或降级跳转到仓内 SSOT 文件/文档），用于“像文件一样查看 preset 内容”。
- 全程保持静态与安全边界：
  - 不执行用户代码；不通过 shell-out CLI 推导语义。
  - 不隐式放宽 allowlist/allowed-roots；所有修复均需用户确认。
  - 失败必须可诊断（trace/降级信息），不得 crash/卡死。

## Capabilities

### New Capabilities

<!-- 本变更优先通过修改既有 LSP/extension/spec 能力实现；不新增 capability spec。 -->

### Modified Capabilities

- `yaml-dsl-editor-semantics-core`: 扩展 shared core 的解析能力，使其可静态解析 `^<id>` / imports 路径 alias / `scalim://...` preset，并产出可诊断的降级信息。
- `yaml-dsl-lsp-server`: 在 definition/hover/completion 上支持上述语法糖，并保证对非 DSL YAML 不污染。
- `yaml-dsl-lsp-code-actions`: 新增/扩展 Quick Fix，使配置缺失（alias/roots 等）可一键引导修复且 workspace-scoped。
- `yaml-dsl-vscode-extension`: 支持打开只读 virtual document（用于 preset 预览），并在 UI 上提供可观测的诊断入口（复用现有日志/状态栏路径）。

## Impact

- shared core：`packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/core.py`
  - sugar 引用解析、hover/definition/completion 的统一入口与降级信息
- LSP server：`packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/server.py`
  - handler 覆盖面扩展（definition/hover/completion/codeAction）
  - 与 codeAction/executeCommand 的协议扩展（如需要）
- VSCode extension：`extras/vscode-scalim/`
  - virtual document scheme/provider（preset 预览）
  - 与 server quick fixes 的 UX 集成（仅 orchestration，不复制语义规则）
