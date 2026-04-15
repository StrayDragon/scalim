## Why

我们在真实用户运行环境中频繁观测到 `scalim.schema` 的 warning：

- `jsonschema 不可用, 已跳过 schema 校验`
- `detail=attrib() got an unexpected keyword argument 'converter'`（依赖版本不匹配导致的 `TypeError`）

该 warning 在 runtime 的 parse/validate 路径中反复出现，造成日志噪音、误报与排障干扰；同时也让 YAML 校验行为在“是否安装/是否兼容 jsonschema”的环境差异下变得不稳定（有的环境更严格，有的环境更宽松）。

鉴于 `scalim` runtime 需要兼容 Python 3.6 且核心包本身不应被可选依赖拖入版本地狱，我们需要把 JSONSchema 校验从框架 runtime 主线彻底移除：runtime 只保留自研语义校验与 unknown-fields 能力；JSONSchema 校验仅保留在工具链（CLI/LSP）的 schema-only 路径中。

## What Changes

- **BREAKING（内部实现）**：`src/scalim/` runtime 的 YAML 校验链路不再导入/使用 `jsonschema`，不再输出“已跳过 schema 校验”的 warning。
- runtime YAML 校验只保留：
  - `ConfigValidator` 的语义校验（SSOT）
  - strict unknown-fields 检测（不依赖 `jsonschema`）
  - parser 层的 fail-fast（类型/必填/枚举等）
- **工具链保留 JSONSchema**：
  - `scalim-cli yaml-dsl schema validate` 继续使用 JSON Schema（依赖 `jsonschema`）做 schema-only 校验
  - LSP/编辑器侧（如需要）继续使用 JSON Schema 提供补全/hover/choices，并可做 schema-only 诊断
- 文档与依赖声明收敛：
  - 明确 `jsonschema` 属于 CLI/LSP 工具链依赖，而不是 runtime core 依赖
  - 在 CLI README/帮助中写清 `schema validate` 的依赖与职责边界

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `framework-logging`: runtime 不再输出 “jsonschema 不可用/已跳过 schema 校验” 的 warning；该类“可选依赖缺失提示”从 runtime 主线移除。
- `yaml-dsl-cli-validation`: `yaml-dsl validate` 的校验分层不再包含 runtime 内置 JSONSchema 校验；JSONSchema 校验仅由 `yaml-dsl schema validate` 承担且由 CLI 发行物显式依赖 `jsonschema`。

## Impact

- **runtime 行为**：`scalim` 在未安装/不兼容 `jsonschema` 的环境中不再产生 schema 相关 warning；YAML 校验结果在不同运行环境下更一致（不再依赖可选依赖状态）。
- **CLI 行为**：
  - `yaml-dsl validate` 仍是语义校验 + unknown-fields（更贴近运行时实际接受/拒绝口径）
  - `yaml-dsl schema validate` 继续提供 schema-only 校验（结构/类型），并保持其输出与编辑器/LSP 的对齐
- **规范与文档**：需要更新相关 OpenSpec 规范（移除/调整“jsonschema 不可用时输出 warning”的要求），并补充 CLI 文档对 `jsonschema` 依赖的明确说明。
