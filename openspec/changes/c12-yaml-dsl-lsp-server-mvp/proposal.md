## Why

`scalim-yaml-dsl-lsp` 已提供 editor/tooling 语义 core，但缺少一个“可被任何编辑器插件拉起”的 LSP server 形态，导致以下能力无法真正落地：

- diagnostics 在真实 YAML 工程（imports/多目录）中的稳定性
- `loader` / `call_by` / `retry.should_retry` 等 Python 引用的跳转、hover、补全
- 面向 VSCode/JetBrains/Neovim/Zed 的统一集成入口（stdio）

本提案的目标是交付一个 **基本完整的 LSP server v1**：跨编辑器可用、静态无副作用、可回归、可排障。

## What Changes

### v1 成功标准（验收口径）
- 任意 LSP client 仅需一个命令（stdio）即可拉起 server 并获得：
  - YAML diagnostics（errors/warnings + range underline）
  - Python 引用 go-to-definition（优先 `loader/call_by/retry.should_retry`）
  - hover（docstring，若可解析）
  - completion（最小可用的符号补全）
- 对常见形态 `call_by: "pkg.mod:fn(arg=...)"`：
  - definition/hover/completion 至少能解析并处理 `pkg.mod:fn`（参数段忽略）
- 任何解析失败 MUST 不崩溃、不退出、不卡死；而是返回空结果 + warnings/logs 供排障。

### P0（必须优先做）

**1) Serve 入口**
- 提供稳定的 server 启动入口：
  - 默认 `stdio`（编辑器集成主路径）
  - 可选 `tcp`（仅 debug；不作为 v1 必选）

**2) Diagnostics**
- `textDocument/didOpen` / `didChange` 驱动 diagnostics：
  - MUST 复用 `scalim_yaml_dsl_lsp.core`（不得 shell-out CLI）
  - MUST 正确映射 range（core 的 1-based -> LSP 的 0-based）
  - MUST 对 imports 扩展遵守 `allowed_yaml_roots`

**3) Python 引用跳转（definition）**
- 至少覆盖字段：
  - `loader`
  - `call_by`
  - `retry.should_retry`（含 `main_source.retry.should_retry`、`sources.*.retry.should_retry` 等常见路径）
- MUST 将 LSP `Position` 映射到 YAML 内的“字段路径 + 字符串值”：
  - 当光标位于上述字段的字符串值范围内时，才触发 definition/hover/completion
  - v1 仅要求覆盖常见的“单行 scalar string”形态（含引号与不带引号）；更复杂的 YAML 光标抽取放到 P2
- 对 `call_by` 支持 `reference(args...)` 形态的“头部解析”：
  - 解析出 `reference` 并复用 core 的 Python 引用解析逻辑

**4) 稳定性与可诊断降级**
- 任意异常 MUST 捕获并降级为可诊断信息：
  - 不退出进程
  - 不返回半截 JSON-RPC
  - 返回空结果 + warnings，并在日志中输出上下文（但不得回显 YAML 正文）

**5) 回归与验证**
- 必须与 `yaml-dsl-lsp-notebooks-regression` 对齐：
  - notebooks fixtures 作为 gate（diagnostics + definition/hover/completion）
- 必须新增 LSP 层集成测试（至少覆盖：启动、open/change、diagnostics、definition 的黄金路径）

### P1（建议在 v1 一并完成，体验会“完整很多”）
- `textDocument/hover`：docstring（若可解析）
- `textDocument/completion`：最小补全（引用字符串内）
- discovery 自诊断输出（日志/可查询入口）：
  - `project_root` / `scalim_yaml_path` / `python_roots` / `allowed_yaml_roots` 摘要
- `scalim.yaml` 变更刷新（至少保证修改后不需要重启即可生效）

### P2（可后置，但必须记录在案）
- `textDocument/codeAction` + `workspace/executeCommand`（Quick Fix）：建议放到独立提案（`yaml-dsl-lsp-server-code-actions`）
- 更复杂的 YAML 光标抽取：
  - 多行字符串、flow 风格、anchors/aliases、复杂引号转义等
- 性能优化（缓存、增量解析、文件监听的更细粒度）
- 多 workspace folders / untitled 文档 / remote URI 等边界

### 依赖与约束（必须明确）
- server MUST 复用 `scalim_yaml_dsl_lsp.core` 作为语义 SSOT：
  - 静态解析（文件系统读取 + AST），不得执行用户代码
  - 不得修改进程级全局状态（例如 `sys.path`）
- `pygls` 依赖归属：
  - 仅作为 server 侧可选依赖（推荐放在 `scalim-yaml-dsl-lsp` 的 `server` extra）
  - 不建议在 repo 根 dev 依赖里直接引入，以免依赖语义漂移

## Capabilities

### New Capabilities
- `yaml-dsl-lsp-serve`: 提供 YAML DSL LSP server 的可启动入口（stdio 为主，可选 tcp），并约束其静态、无副作用与可诊断降级行为。

### Modified Capabilities
- `yaml-dsl-lsp-server`: 将 v1 MVP 的 LSP 能力边界固化为明确 contract（diagnostics + Python 引用 definition/hover/completion），并要求语义复用 shared core。

## Impact

- 受影响代码/资产（预期）：
  - `packages/scalim-yaml-dsl-lsp/`：新增 server 层与 entrypoint（pygls），保持 core 为 SSOT
  - `tests/`：新增 LSP 集成测试 + 与 notebooks fixtures 的回归门禁联动
- 运行时边界：
  - server 运行时可要求 Python 3.10+（与 `scalim-yaml-dsl-lsp` 包一致），不得影响 `scalim` 本体的 Python 3.6 运行时边界
