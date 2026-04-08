## Why

YAML DSL 的 authoring 面经常使用 anchors/aliases（例如 `_templates` 片段复用）、nested list flatten（例如 `outputs[*].fields: - *detail_fields`）、以及 `imports/$import` 复用来降低重复与收敛语义边界。但这些“运行时/validator 能理解的展开语义”在编辑器中常被当作普通 YAML 字符串/结构，导致：

- `outputs[*].fields` 等字段列表无法对 field_id 提供 hover/definition/completion。
- 通过 alias/template 复用的字段列表，在编辑器里难以“看见展开后的有效结果”，排障与对拍成本高。
- LSP 若用 naive 的“每次请求全量解析/展开”会在大工程下卡顿，且无法稳定复用同一份展开结果。

## What Changes

- 引入面向 editor 的“有效配置（effective）展开”能力（静态无副作用）：
  - 以当前打开文档的 **内存态 YAML 文本** 作为输入（不依赖 mtime）。
  - 支持 anchors/aliases、merge key 与 DSL 约定的 nested list flatten（至少覆盖 `outputs[*].fields`）。
  - 对 demand YAML 支持基于现有库侧 API 的 imports/$import 展开（受 allowed-roots 约束），并为后续语义能力提供可复用的“有效 mapping”视图。
- 在 LSP 语义中使用展开结果提升“可导航性”：
  - `outputs[*].fields` 内的 field_id：hover 展示字段摘要；F12 跳转到字段定义（可能在主文件或 fragment 文件）；completion 补全可用 field_id。
  - 当字段列表来自 alias（如 `*detail_fields`）时：在 alias 位置支持 definition/hover（跳到 anchor 定义，并解释展开后的元素规模/摘要）。
- 引入高效缓存与失效策略（面向实时编辑）：
  - 以 `document_uri + document_version`（或等价文本 hash）缓存 ruamel.yaml parse 与展开产物。
  - 对 imports 展开涉及的 fragment 文件：按 `(path, mtime_ns)` 缓存解析/位置索引，并对并发请求做 in-flight 去重。
  - 保持 fail-fast 且可诊断的降级：展开失败时返回空结果 + 可解释原因，不 crash、不阻塞编辑器。
- 性价比策略（便于决定做/不做与如何分阶段）：
  - Phase 1（高 ROI）：仅覆盖 anchors/aliases + nested list flatten + 同文件 field 定位，先把 `outputs[*].fields` 的导航体验补齐。
  - Phase 2（中 ROI）：按需接入 imports/$import 的 fragment 读取与定位（受 allowed-roots 约束），把“字段定义在 fragment 文件里”的场景打通。
  - Phase 3（低 ROI/高成本）：如果需要“完全等价的 effective YAML”与跨文件 symbols/preview，再讨论 source-map 级别的全量展开与可逆定位。

## Capabilities

### New Capabilities

<!-- 本变更优先扩展既有 editor/LSP 能力；不新增 capability spec。 -->

### Modified Capabilities

- `yaml-dsl-render-effective-yaml`: 在不改变“库侧 SSOT API”语义的前提下，为 editor 场景补齐可复用的展开入口与可诊断错误信息约束（必要时扩展为支持 source-trace/fragment 定位的输出形态）。
- `yaml-dsl-editor-semantics-core`: 增加“基于有效展开视图”的字段索引/定位能力，支撑 outputs 字段列表的 hover/definition/completion。
- `yaml-dsl-lsp-server`: 使用 shared core 的展开结果，为 `outputs[*].fields`（及其 alias 展开）提供导航与补全，并保证对非 DSL YAML 不污染。

## Impact

- shared core：
  - `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/core.py`：新增/扩展 effective expansion + 输出字段列表导航的语义入口。
  - `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/cursor_extraction.py`：扩展光标抽取，覆盖 outputs.fields 场景（含 alias token 的 range）。
- scalim library（复用，不复制语义）：
  - `src/scalim/dsl/yaml_dsl/_internal/config_parsing/effective_yaml.py`：作为 imports/$import 展开的 SSOT（editor 侧调用时必须保持静态与安全边界）。
  - `src/scalim/dsl/yaml_dsl/_internal/config_parsing/parsers/outputs.py`：复用 nested list flatten 与字段引用解析的既有规则，避免 editor/runtime 语义漂移。
