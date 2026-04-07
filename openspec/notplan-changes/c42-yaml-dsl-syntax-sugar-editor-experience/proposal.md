## Why

YAML DSL 为了降低“写起来很啰嗦”的成本，引入了一些语法糖/快捷方式，例如：

- 内置 callable：`^<id>`（示例：`^workflow/book_sheet_rows`）
- imports 路径 alias：`@/x.yaml`、`COMMON:/x.yaml`（依赖 `scalim.yaml` 的 `import_aliases`）
- 内置 preset：`scalim://yaml-dsl/presets/common.yaml`

运行时这些能力能显著提升可复用性与安全边界，但编辑器体验如果没跟上，会出现“能跑但不好写/不好查/不好跳”的落差：

- 用户不知道有哪些 `^<id>` 可用、怎么补全、也无法跳转到实现或文档。
- `imports` 写了 `@/..`，如果 alias 没配置，用户只看到一个报错字符串，不知道应该改哪里。
- `$import` 指向 `scalim://...` preset 时，hover/definition 目前只能降级为 explain，无法“像文件一样打开看看”。

本提案聚焦：**让这些语法糖在 LSP/VSCode 中具备同等“可探索性”与“可排障性”。**

## Goals

- **G1：可探索**：用户能通过 completion/hover 快速理解 sugar 的含义与可用值。
- **G2：可跳转**：尽可能提供 definition（打开实现/打开 preset 内容/打开 fragment 文件）。
- **G3：可修复**：当 sugar 因配置缺失而失败时，提供 Quick Fix 指向正确的修复位置（通常是 `scalim.yaml`）。
- **G4：不破坏护栏**：保持静态无副作用；不执行用户代码；不扩大 imports allowed-roots 的安全边界。

## Non-Goals

- 不把 “runtime 注入的 builtin_callables（RunOptions）” 完整暴露到编辑器（除非有明确、安全的配置入口）。
- 不在 editor 侧隐式放宽运行时约束（allow-roots/allowlist 仍以运行时校验为准）。

## Proposal（按语法糖拆分）

### 1) `^<id>` builtin callable：definition / hover / completion

#### Reference Forms

- loader：
  - `main_source.loader: ^workflow/book_sheet_rows`（`^<id>` 表示以 `^` 开头的 builtin id）
  - `sources.*.loader: ^workflow/book_sheet_rows`
- call_by（忽略参数段定位）：
  - `fields.*.call_by: "^workflow/book_sheet_rows(ref)"`（string）

#### Trigger Forms

- Completion：在 `^` 后触发（Ctrl+Space + 自动提示）
- Hover：悬停在 `^<id>` 上
- Go to Definition：F12

#### Expected Behavior（推荐）

1) Completion
- 列出“框架内置的保守词表”中的 builtin ids（例如 `workflow/book_sheet_rows`）
- 显示简短说明（例如一行 summary）
- 对 call_by 位置提供 snippet：`^workflow/book_sheet_rows(${1:arg}=${2:value})`

2) Hover
- 展示：
  - builtin id
  - 简短说明（若有）
  - 若能映射到 Python 引用：展示解析后的 python ref（但不执行）

3) Go to Definition（多 locations）
- **首选**：跳到该 builtin 对应的 Python 实现（若可映射为 python ref 且能静态解析到文件/符号）。
- **备选**：跳到 builtin 词表/文档位置（例如仓内文档或 spec 的对应段落）。
- **降级**：返回空 + warnings（同时给出“可用 id 列表入口”的指引）。

#### Options & Trade-offs（builtin 词表来源）

Option A（推荐默认）：只支持“框架内置保守词表”
- 维护性：高（SSOT 在 `scalim` 内部；编辑器只读）
- 性能：高（列表小）
- 体验：对 80% 场景足够；下游自定义 builtin_callables 无法补全/跳转

Option B：允许在 `scalim.yaml` 声明“editor 扩展词表”
- 维护性：中（需要定义配置 schema + 与运行时注入的边界）
- 性能：中（取决于词表大小）
- 体验：强（下游团队可以把常用 builtin 暴露给编辑器）
- 风险：需要明确“不意味着运行时允许执行任意模块”，只是一份“可解析到 python ref 的词表”

### 2) `imports` 路径 alias：`@/x.yaml` 与 `ALIAS:/x.yaml`

#### Background

imports 的文件路径本质上是**相对路径**，但通过 `scalim.yaml` 的 `yaml_dsl.import_aliases` 可以引入目录别名：

- `@/x/y.yaml`（alias 以 `@` 开头时使用 `@/` 语法）
- `COMMON:/x/y.yaml`（一般 alias 使用 `ALIAS:/` 语法）

如果 alias 未配置，运行时/编辑器都必须 fail-fast（安全边界），但 editor 侧应该给出更“行动导向”的提示。

#### Reference Forms

```yaml
imports:
  common: "@/fragments/common.yaml"
  shared: "COMMON:/fragments/shared.yaml"
```

#### Trigger Forms

- Hover：悬停在 `imports.*` 的 value 字符串上
- Go to Definition：F12（对 imports value 或 `$import` 引用）
- Completion：在 value 内输入 `@/` 或 `ALIAS:/` 时触发
- Quick Fix：当解析失败时提供（灯泡）

#### Expected Behavior（推荐）

1) Hover（imports value）
- 展示 raw path、alias 匹配结果、resolved path、以及 allow-roots 校验结果（通过/失败原因）。

2) Go to Definition（imports value）
- 直接跳到 fragment 文件本身（文件起始即可）。

3) Completion（imports value）
- 在开头补全：
  - `./`、`../`、`<dir>/...`（相对路径）
  - 已配置的 alias 前缀（例如 `@/`、`COMMON:/`）
- 在 alias 已确定后，按 alias 对应 base_dir 做相对路径补全（只补 `.yaml/.yml`）。

4) Quick Fix（当 alias 未配置）
- “Add import alias `@` to scalim.yaml”（写入 `yaml_dsl.import_aliases`）
- 同步建议（可选）：把该目录加入 `import_allowed_roots`（或提示用户为何可能需要）
- fix 必须是 workspace-scoped；越界则降级 explain-only

#### Options & Trade-offs（alias 默认值）

Option A（推荐）：不引入任何“隐式默认 alias”
- 安全与一致性最好；用户必须显式在 `scalim.yaml` 配置 `@` 或 `COMMON`
- 成本：首次配置门槛略高，但可被 Quick Fix 抵消

Option B：把 `@` 作为隐式 alias（例如 project_root）
- 体验：更开箱即用
- 风险：会让 allow-roots 边界更隐晦；也可能与既有团队约定冲突

### 3) `scalim://...` preset：可打开/可跳转

#### Reference Forms

```yaml
imports:
  common: "scalim://yaml-dsl/presets/common.yaml"
```

#### Expected Behavior（推荐）

1) Hover
- 显示 preset id、来源（只读、本地白名单）、以及“如何查看内容”的入口（命令/链接）。

2) Go to Definition
提供两种可行实现路线（择一）：

Option A：Virtual Document（推荐）
- definition 打开一个只读虚拟 URI（例如 `scalim-preset://yaml-dsl/presets/common.yaml`）
- 内容为 preset YAML 文本（带“Generated, read-only”提示）
- 优点：体验最好（像打开文件一样）
- 风险：需要 client（VSCode）对自定义 scheme 的打开支持（可能需要 extension 辅助）

Option B：跳到仓内 SSOT 文档/源文件
- 如果 preset 对应仓内某个真实文件（或 docs 页），definition 直接打开它
- 优点：实现简单、跨 editor 兼容更好
- 缺点：用户无法直接看到“运行时实际加载的 YAML 文本”（可能存在渲染/合并差异）

## 关于 `^<scalim:...>`（命名空间写法的建议）

现状：builtin callable id 语法（`^<id>`）默认只允许 `[A-Za-z0-9_]+` 与 `/` 分段；不支持 `:`。

如果团队确实需要“显式命名空间”（例如区分 `scalim` 内置与下游自定义），有两种更稳的路径：

1) **不改语法**：使用前缀分段模拟命名空间（推荐）
- 例如：`^scalim/workflow/book_sheet_rows`
- 优点：无需变更解析规则/JSON schema pattern；兼容成本最低

2) **扩展语法**：允许 `:` 作为命名空间分隔（例如 `^scalim:workflow/book_sheet_rows`）
- 优点：更贴近用户直觉
- 成本：需要同步更新 `reference_syntax.py`、schema pattern、文档与 LSP 解析；并明确与 `module:attr` 的 `:` 不冲突（因为 builtin 总以 `^` 开头）

推荐结论：优先采用方案 1；只有当用户已大量使用 `^scalim:...` 且迁移成本不可接受时，再考虑方案 2。

## Validation（fixture 覆盖建议）

- `^<id>`：
  - loader/call_by 两类位置；
  - completion 列表稳定排序；
  - definition 返回（python impl + 文档备选）；
  - unknown id 的诊断与提示。
- imports alias：
  - `@/` 与 `ALIAS:/` 两种 token；
  - alias 未配置 / 配置但越界 / 文件不存在；
  - hover 的 resolved path 与 allow-roots trace。
- preset：
  - hover explain；
  - definition 打开虚拟文档或 SSOT 文件。

## Impact（涉及模块）

- shared core：`packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/core.py`
- 运行时语法（若采纳 `^scalim:...` 扩展）：`src/scalim/dsl/by_yaml/reference_syntax.py` + schema generator + docs
- specs（后续转正时）：
  - `openspec/specs/yaml-dsl-builtin-callables/spec.md`
  - `openspec/specs/yaml-dsl-imports/spec.md`（或相关 imports/presets spec）
  - `openspec/specs/yaml-dsl-lsp-server/spec.md`
