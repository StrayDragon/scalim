## Context

- 运行时已支持的“关键语法糖”在编辑器侧存在落差:
  - builtin callable 引用: `^<id>`
  - imports 路径别名: `@/x.yaml`、`ALIAS:/x.yaml`（依赖 `scalim.yaml` 的 `yaml_dsl.import_roots`/aliases）
  - preset: `scalim://...`
- LSP 现状:
  - Python 引用解析 `resolve_python_definition` 对 builtin callable 直接降级（warnings）；
  - `$import` 引用（`alias.seg...`）已支持 hover/definition，但对 `imports.*` value（path 本身）尚无 completion/hover/definition；
  - preset 当前只识别为 kind，但缺少“像文件一样打开”的体验。

约束/护栏:
- 全程静态无副作用：不执行用户代码，不 shell-out。
- 不隐式放宽 allow-roots/allowlist；所有“修复配置”的动作必须用户确认。
- 对非 DSL YAML 不污染（feature gate 仍以 DSL 判定为前置）。

## Goals / Non-Goals

**Goals:**
- `^<id>`: completion/hover/definition（尽量定位到 Python 实现或 SSOT 文档）。
- imports alias path（`imports.*` value）: completion/hover/definition + Quick Fix（引导修复 `scalim.yaml`）。
- `scalim://...` preset: hover + definition（virtual document 只读预览）。
- 失败必须可诊断（与 `yaml-dsl-lsp-resolution-infra` 的 trace/降级信息对齐）。

**Non-Goals:**
- 不把“运行时动态注入 builtin_callables（RunOptions）”完整暴露到编辑器，除非有明确、安全的配置入口。
- 不在 editor 侧改变运行时约束（allowed-roots 等仍以运行时为准）。

## Decisions

### 1) 统一 sugar 解析入口: “cursor → kind → resolver”

- 在 `cursor_extraction.py` 扩展三类抽取:
  1. builtin callable token（以 `^` 开头，出现在 `loader`/`call_by` 等位置）
  2. imports mapping value（`imports.<alias>` 的 value scalar）
  3. preset URI（`scalim://...`）
- shared core 为每一类提供 resolver:
  - `resolve_builtin_callable_semantics(...)`
  - `resolve_import_path_semantics(...)`
  - `resolve_preset_semantics(...)`
- server 层在 definition/hover/completion 中统一走“kind 分发”，避免重复 if/else。

### 2) builtin callable: 保守词表 + 可追溯映射

- 词表来源选择:
  - 推荐 SSOT 在 `scalim` 代码库（runtime 拥有 builtin 概念），对外暴露一个“只读、保守”的 editor 词表接口（避免 LSP/extension 自己维护 drift）
  - LSP 侧仅消费该列表，产出 completion/hover/definition
- definition 策略:
  - 若 builtin id 可映射为 Python reference（字符串），直接复用 `resolve_python_definition`，并返回多 locations（排序由 `yaml-dsl-lsp-resolution-infra` 统一）
  - 若无法映射，则返回空 + hover/trace 指向“查看词表/文档入口”

### 3) imports alias path: `imports.*` value 的 completion/hover/definition

- 解析规则 SSOT 复用 runtime imports 逻辑（`scalim.dsl.yaml_dsl._internal.config_parsing.imports`）:
  - alias 重写来自 `scalim.yaml yaml_dsl.import_roots[*].alias`
  - allowed-roots 约束来自 discovery + `import_roots[*].path`
- hover:
  - 展示 raw path / alias 匹配结果 / resolved path / allow-roots 校验结果（成功或失败原因）
- definition:
  - 若解析为本地文件路径，跳转到 fragment 文件（文件级即可）
- completion:
  - 起始补全：`./`、`../`、已配置 alias 前缀（`@/`、`COMMON:/` 等）
  - 当 alias 前缀确定后：在对应 base_dir 下补全 `.yaml/.yml` 相对路径
  - 性能护栏：只在用户触发 completion 时做目录枚举，并受 allowed-roots 限制

### 4) Quick Fix: “alias 缺失/越界”一键引导（workspace-scoped）

- 以 provider 模式接入（依赖 `yaml-dsl-lsp-resolution-infra` 的 Quick Fix registry）。
- 触发条件来源:
  - imports path 解析失败的结构化 reason（trace）或稳定的 error code（推荐）
  - 兼容兜底：解析失败 warnings 文本的特征匹配（仅过渡期使用）
- 修复动作:
  - 向 `scalim.yaml yaml_dsl.import_roots` 追加条目（`{path: <dir>, alias?: <alias>}`）
  - 最小/宽松两档策略与现有“修复 import_roots”保持一致（减少 UX 分叉）

### 5) preset: Virtual Document（只读）统一方案

- preset 文本来源 SSOT:
  - runtime 已有 `load_scalim_preset_yaml_text(preset_id)`
  - server 提供 `workspace/executeCommand`（例如 `scalim.preset.getText`）返回 YAML 文本（不回显用户 YAML）
- VSCode 侧:
  - 通过 `TextDocumentContentProvider` 注册 `scalim-preset://` scheme
  - definition 返回该 URI，用户像打开文件一样查看（只读）
- Virtual docs 基础设施约束（为后续复用预留）:
  - VSCode 侧只维护一个 provider 实例，并可按需对多个 scheme 复用注册（本变更先落 `scalim-preset://`；`scalim-effective://` 等留给后续变更）。
  - server 侧建议统一虚拟文档取内容协议（`workspace/executeCommand` 返回 `{content, title, languageId}`），避免后续 route 增长时协议分裂。

### 6) 文档/生成边界与 drift gates（必须）

- 手工编辑范围:
  - `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/**`
  - （如需）`src/scalim/dsl/yaml_dsl/_internal/**` 中的 SSOT 词表/解析逻辑
  - `extras/vscode-scalim/src/**`（仅当实现 virtual document provider）
- 禁止手改:
  - 任意 `*.gen.*` 与 `BEGIN/END AUTOGEN:*` 区块内部
  - `extras/vscode-scalim/dist/**`、`extras/vscode-scalim/out/**`
- Drift gates:
  - `just qa`
  - `just openspec-check`

## Risks / Trade-offs

- [builtin 词表 drift] → 把词表放到 runtime 作为 SSOT；LSP/extension 只消费。
- [路径补全的 IO 成本/安全边界] → 只在 completion 触发时枚举目录；严格限制在 allowed-roots 下；缓存 `(path, mtime_ns)`。
- [Quick Fix 误修复扩大边界] → 修复动作必须用户确认；默认提供“最小修复”选项；tooltip 明确影响（允许的 imports roots 变化）。
