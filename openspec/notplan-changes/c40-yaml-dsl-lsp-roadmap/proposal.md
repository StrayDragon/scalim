## Why

我们的 YAML DSL LSP 已经能显著提升写 YAML 的效率（diagnostics / hover / completion / go-to-definition / quick fix），但随着用户把 DSL 用到更多真实工程场景，问题开始从“单点能力缺失”变成“覆盖面与一致性”：

- **语法覆盖面**：不仅是 `module:func`，还包含 `$import`、`module:obj.method`、`^<id>` 内置 callable、`scalim://...` preset、以及各种 alias/path sugar。
- **YAML 内部跳转**：用户更常见的导航目标其实是 YAML 自身的实体（`sources/fields/relations/outputs/...` 的 ID 引用），而不是 Python。
- **排障体验**：解析失败时“能解释、能修复、能自助”比“勉强给个空结果”更重要（例如缺 `scalim.yaml`、roots 不对、imports 越界、路径 alias 未配置）。
- **性能与稳定性**：在大型 monorepo、多 python_roots、多 imports 的工程下，必须把“静态解析 + 缓存 + 可诊断降级”打磨成可靠底座。

因此需要一个**面向 LSP 的 roadmap 提案**：把现有能力从 MVP 扩展为“覆盖全面 + 可诊断 + 可演进”的编辑语义平台。

## Current State（简述）

当前 LSP server（pygls）遵循既有约束：

- 语义 SSOT 在 shared core（`scalim-yaml-dsl-lsp`），server 层不复制规则。
- 解析为纯静态：不执行用户代码、不 shell-out CLI。
- 已支持的关键能力：
  - demand/workflow 的 diagnostics（workflow v1 schema-only）。
  - Python 引用字段的 definition/hover/completion（支持绝对/相对模块引用；`module:obj.method` 已做静态推断并可返回多个 locations）。
  - `$import` 的 definition/hover（仅 file fragment；preset 目前降级为 explain）。
  - codeAction + executeCommand（用于 discovery/roots 的 Quick Fix 与 explain）。

本提案只做 roadmap，不在此 change 内实施。

## Goals

- **G1：覆盖面**：把 DSL 常见“引用形态”纳入同一套解析/定位机制，减少“某些字符串能跳转、某些不能”的割裂感。
- **G2：YAML-native 体验**：让 DSL 内部 ID 引用（source/field/relation/output/workflow run 等）也具备定义/引用/补全/hover。
- **G3：可诊断降级**：任何失败都要给出可理解的原因 + 可执行的修复入口（Quick Fix / 命令）。
- **G4：可维护与可测**：每个新增解析分支都必须能用 fixture 覆盖，并能在 core 单测 + LSP e2e 中验证。
- **G5：性能**：在大工程下保持可用（缓存、懒加载、限流、按需索引）。

## Non-Goals

- 不引入执行期语义（不运行 Python / 不跑 workflow compile）。
- 不替代 `redhat.vscode-yaml` 的 schema 校验（只做互补：语义 + 导航 + quick fix）。
- 不承诺“一步到位全 workspace 索引”；优先做“按需、可诊断、渐进增强”。

## Roadmap（分阶段）

### Phase 0：把“基础引用”做成可靠平台（高收益 / 低风险）

**目标**：definition/hover/completion 在更多引用形态下稳定工作；失败时可解释；大项目不卡顿。

1) 引用解析覆盖面扩展（静态、可降级）
- Python 引用：继续扩展更多“可静态判定”的写法（见 `c42-...` 的 builtin 与 sugar 部分）。
- `$import`：补齐对 `scalim://...` preset 的 editor 侧可导航体验（至少 hover explain；理想是可打开虚拟文档）。

2) 结果质量：多 locations + 稳定排序 + 可控去重
- 对所有“可产生备选定位点”的解析：统一返回**多个 locations**，并规定稳定排序：
  1. 最具体/最接近真实实现的位置（例如 `Klass.method`）
  2. 次优的声明点（例如 `obj = Klass()`）
  3. import re-export / alias / stub 等“信息含量更低”的位置

3) 性能：缓存与限流（不改变语义）
- AST/文件读取缓存（按 path + mtime/版本号）；
- imports fragment YAML 解析缓存；
- LSP 请求并发控制（避免多个 hover/definition 抢 IO）。

4) 排障：把“为什么失败”结构化
- 统一输出 “resolution trace”（例如：发现了哪些 roots、模块文件选中了哪个、为何 rejected）；
- 对常见失败提供 Quick Fix（补 roots、创建 `scalim.yaml`、扩大 allow-roots 等）。

### Phase 1：YAML-native 导航（定义/补全/hover）

**目标**：让 DSL 像一门“有符号系统”的语言，而不是一堆 YAML 字段。

1) Go to Definition（YAML 内部）
- `fields.*.source` → `sources.<source_id>`
- `fields.*.relation: <relation_id>` → `relations.<relation_id>`
- `relations.*.steps[*].from/to: <source_id>.<field_id>` → 对应 source/field 的声明点
- `outputs[*].from: <output_id>`（若语义存在）→ output 定义点
- workflow（若开启）：`depends_on` / `main_rows_from.run` 等 ID → 对应 run 节点

2) Completion（ID 与关键路径补全）
- 在 `source:` 处仅补全已存在的 `sources` keys；
- 在 `relation:` 处仅补全 `relations` keys；
- 在 `from/to` 的 `source_id.` 后补全该 source 下可用 field id；
- 支持 snippet：例如输入 `a.` 自动补全为 `a.<field_id>`。

3) Hover（摘要）
- Hover 在 `source_id` / `relation_id` / `run_id` 上显示“被引用实体摘要”（loader、key、字段数量、位置等）。

4) Document Symbols / Outline
- 提供 YAML DSL 结构大纲：Sources / Fields / Relations / Outputs（可折叠、可跳转）。

### Phase 2：Refactor 级能力（rename / references / extract）

**目标**：把常见“结构性修改”变成可安全批量操作的编辑器能力。

1) Rename（安全重命名）
- 重命名 `source_id`：同步更新所有引用位置（`fields.*.source`、relations steps 等）。
- 重命名 `relation_id`：同步更新 `fields.*.relation` 引用。
- 重命名 output id / workflow run id（如适用）。

2) Find References（引用查找）
- 文档内 references：精确列出所有引用点；
- workspace references（可选、后置）：在允许范围内跨文件扫描（需明确性能策略）。

3) Code Actions：结构化重构辅助
- “Extract fragment”：把一段 mapping 提取到 fragment 文件 + 自动生成 `imports` 与 `$import`；
- “Inline import”：将 `$import` 展开为本地 YAML（仅编辑器侧，保留可撤销 edit）。

## Reference Forms（覆盖面清单）

本 roadmap 关注的“引用/跳转”形态至少包括：

- Python callable 引用字段：
  - `loader: "<py-ref>"`
  - `call_by: "<py-ref>(...)"`（忽略参数段进行定位）
  - `normalize.call_by: "<py-ref>(...)"`（如 schema 支持）
- 内置 callable（详见 `c42-...`）：
  - `loader: "^<id>"`
  - `call_by: "^<id>(...)"`
- YAML imports：
  - `imports: {alias: "<fragment-path | scalim://preset>"}`
  - `$import: "<alias>(.<segment>)*"`
- YAML ID 引用：
  - `fields.*.source / relation`
  - `relations.*.steps[*].from/to`
  - workflow run DAG 引用（若启用）

## Trigger Forms（用户触发方式）

- Go to Definition：F12 / Cmd+Click / Peek Definition
- Hover：鼠标悬停 / `editor.action.showHover`
- Completion：Ctrl+Space（或自动触发）
- Quick Fix：灯泡（`textDocument/codeAction`）
- Command：命令面板（`workspace/executeCommand`）

## Options & Trade-offs（维护性 / 性能 / 体验）

1) On-demand vs Index-first
- **On-demand（推荐默认）**：只在用户触发时解析；实现简单、性能可控、失败可解释。
- Index-first：启动后扫 workspace 建索引；体验强但成本高（I/O、缓存一致性、错误面更大）。

2) Workspace references 的范围
- 文档内 references（推荐先做）：可靠、成本低、用户马上受益。
- 跨文件 references：需要清晰的 allow-roots + 扫描边界，否则容易慢/噪声大。

3) 解析精度 vs 实现复杂度（Python 侧）
- AST 静态推断只做“可靠子集”（推荐）：宁可返回多个候选 locations，也不做高风险猜测。
- 深度类型推断（不推荐作为近期目标）：容易引入不稳定与性能问题。

## Validation（fixture 与验收口径）

- core 单测（纯函数）：
  - Python 引用解析：覆盖 `module:obj.method`、import alias、builtin、失败降级。
  - `$import`：file/preset/alias path、越界/不存在、片段非 mapping。
  - YAML ID 跳转：source/relation/run 等。
- LSP e2e：
  - 打开 YAML → 请求 definition/hover/completion → 断言 locations/ranges 稳定；
  - 多 roots / 多文件 imports 的性能冒烟（限时）。

## Impact（涉及模块）

预期主要触点：

- shared core：`packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/core.py`
- server：`packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/server.py`
- 规格演进（后续转正时）：
  - `openspec/specs/yaml-dsl-lsp-server/spec.md`
  - `openspec/specs/yaml-dsl-lsp-code-actions/spec.md`
  - `openspec/specs/yaml-dsl-editor-semantics-core/spec.md`
