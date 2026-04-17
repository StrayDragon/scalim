## Why

当前 YAML DSL 的 authoring 体验存在两类“高频但低价值”的摩擦:

1) **字符串引号噪音**
   在 `loader` / 顶层派生字段 `compute` / `call_by` 等位置,大量示例与产物倾向于写成 `"xxx"`。这不会增加语义信息,但会:
   - 降低可读性（尤其是 `call_by` 的长参数列表）
   - 增加 diff 噪音（改一个参数会触发整行变化）
   - 让用户误以为“必须加引号”才合法

2) **可读性与可跳转能力互相牵制**
   目前 LSP 的 `loader/call_by` 引用跳转/补全主要覆盖单行 scalar;一旦用户为了可读性改用 YAML block scalar（`|` / `>`）把 `call_by` 拆成多行,就会失去跳转/补全能力。
   同时,框架 core 的 `call_by` 解析对“多行参数 + Python 风格 `#` 注释”存在语法陷阱,导致用户无法稳定写出“可读且可注释”的调用形态。

因此需要一个“团队可执行的统一入口”：
- 通过 `scalim-cli yaml-dsl` 提供类似 ruff 的 **lint/format** 工具,把风格从“口头约定”收敛为可自动执行的规则；
- 同步补齐 core + LSP 对 multiline `call_by` 的基础支持,避免工具鼓励的写法在编辑器里反而不可用。

## What Changes

- 新增 `scalim-cli yaml-dsl lint`：对 YAML DSL 做**风格与可维护性**检查（不替代 `validate` 的语义校验）。
  - 默认仅报告；支持 `--fix`（仅执行确定性、安全的修复）。
  - 首批聚焦“引号风格”“多行 call_by 可读性”“高风险 plain scalar（会被 YAML 解释为非 string）”等规则。
- 新增 `scalim-cli yaml-dsl format`（可选别名 `fmt`）：对 YAML DSL 执行**幂等格式化**。
  - 目标是把 `loader/call_by/compute` 的 “可安全 plain scalar” 输出为不带引号的写法。
  - 保留/保护语义：遇到会触发 YAML 隐式类型（如 `true/false/null/123`）或包含 YAML comment 触发点等情况,必须保留引号。
- 框架 core: 扩展 `call_by` 解析以支持 multiline 参数中的 Python 风格 `#` 注释（不改变既有无注释写法）。
- LSP: 扩展 cursor extraction/definition/hover/completion,支持在 YAML block scalar（`|`/`>`/`|-`/`|+` 等）内对 `loader/call_by` 进行跳转与补全（以“可跳转 item”为目标,不要求完整 range 覆盖整段 block）。
- 文档/skill 示例对齐:
  - 将示例与 canonical YAML 的风格基准调整为“尽量不写引号”（由 format 工具保障一致性）。
  - `agentdev/skills` 的受控产物由生成链路更新,不手改生成物。

## Capabilities

### New Capabilities

（无新增独立 capability；本变更聚焦在既有 YAML DSL 工具链与编辑器体验上扩展 requirements。）

### Modified Capabilities

- `yaml-dsl-public-tools`: 增加/规范 `yaml-dsl lint` 与 `yaml-dsl format` 的 CLI 行为、退出码与稳定输出格式。
- `field-compute`: `call_by` 的解析规则扩展为接受 multiline 参数内的 Python 风格 `#` 注释,并保证注释不影响括号匹配与参数绑定。
- `yaml-dsl-editor-semantics-core` + `yaml-dsl-lsp-server`: `loader/call_by` 的引用抽取逻辑从“仅单行 scalar”扩展到 block scalar,并保持对 partially-valid YAML 的降级稳定性。
- `yaml-dsl-agent-guidance` / `yaml-dsl-lsp-editor-integration-guides`: 推荐写法与示例更新为“plain scalar 优先 + 长 call_by 用 block scalar”,避免与工具链不一致。

## Impact

- **CLI/Tooling**
  - 代码主要影响: `packages/scalim-cli/src/scalim_cli/yaml_dsl.py`（新增子命令）、以及可能的共享格式化/规则模块。
- **Runtime (Python 3.6 boundary)**
  - `src/scalim/dsl/yaml_dsl/_internal/config_parsing/call_by.py`（解析与校验）需保持 3.6 兼容。
- **LSP (独立 PyPI 包, Python>=3.10)**
  - `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/cursor_extraction.py` 等模块（multi-line 支持 + range 计算策略）。
- **Docs / Skills governance（SSOT vs generated）**
  - 生成物: 任何 `*.gen.*` 与 `agentdev/skills/scalim-yaml-dsl/references/generated/**` 禁止手改。
  - skill 生成入口: `scripts/gen-agent-skill.py`（SSOT 示例来源包含 `notebooks/marimo/.../declared_yaml_dsl/ecommerce_report.yaml`）。
  - docs-site 注入/生成入口: `just gen-docs`（含 `<!-- BEGIN/END AUTOGEN:... -->` 区块）。
  - 本变更落地后应将示例风格统一交由 `yaml-dsl format`/生成脚本保障,减少手工维护成本。

