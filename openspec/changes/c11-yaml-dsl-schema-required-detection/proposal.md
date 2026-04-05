## Why

当前 VSCode 扩展/LSP 在“是否启用 Scalim YAML DSL 语义、应绑定 demand 还是 workflow schema”上仍存在一定漂移风险：探测逻辑依赖硬编码 key hint / 文件路径约定 / 文本启发式，容易随着 DSL 演进或用户目录结构变化而误判。

我们希望把“这是 Scalim DSL / 它属于 demand 还是 workflow”的判定尽量收敛到 schema 这一单一事实来源（SSOT），并在不引入额外配置成本的前提下提升 0-config 可用性与可维护性。

## What Changes

- 扩展与 LSP server 的 YAML 类型探测（is DSL?）与类型分类（demand/workflow）将优先依据内置 JSON Schema 的顶层 `required` 字段：
  - demand: `required=["name","main_source"]`
  - workflow: `required=["workflow"]`
- VSCode 扩展在进行 `yaml.schemas` 绑定时，将基于上述分类结果对单文件进行 schema 选择（demand/workflow），并保留必要的 fallback 以兼容“正在编写中的 YAML”尚未具备完整 required 字段的场景。
- LSP server 侧将与扩展使用同一套分类原则，以避免出现“schema 绑定为 demand 但 LSP 当作 workflow（或反之）”的体验不一致。
- 仅做探测/分类层的对齐，不引入白名单目录/显式 allowlist 配置（用户可通过禁用扩展临时规避误触发）。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `yaml-dsl-vscode-extension`: schema 绑定与自动启用的判定依据由启发式升级为 schema(required) 驱动，并与 LSP 分类保持一致。
- `yaml-dsl-editor-project-discovery`: 默认类型分类启发式将补充 schema(required) 作为更稳定的 SSOT 信号（并保留对不完整 YAML 的降级策略）。
- `yaml-dsl-lsp-server`: 对“何时对一个 YAML 提供 DSL diagnostics/definition/hover/completion”的判定将与 schema(required) 对齐，降低对非 DSL YAML 的污染风险。

## Impact

- 影响范围：
  - `extras/vscode-scalim/`：文档类型探测、单文件 schema 绑定策略
  - `packages/scalim-yaml-dsl-lsp/`：editor semantics core 的类型分类与 server 侧 gating
  - `openspec/specs/`：上述能力的 requirements 需要同步更新（spec-driven）
- 风险与回滚：
  - 若 required-based 探测过于严格导致“未写全的 YAML 无法触发 LSP”，需确保存在 DSL 专属语法（如 `$import/$init_var`、`loader/call_by`）的 permissive fallback。
  - 行为变更主要体现在“何时自动启用/绑定哪种 schema”，不改变 DSL 语法本身；必要时可通过回滚相关 commit 恢复旧启发式。

