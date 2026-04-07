## Why

c41 补齐了 VSCode 扩展的"可观测与可排障"能力（日志、Status Bar、Doctor、Setup Wizard）。但在日常使用中，用户还需要更丰富的**可视化 UI**来理解 DSL 结构、查看解析结果、浏览可用修复：

1. **结构大纲缺失**：用户无法一览当前 YAML 文件的 sources / fields / relations 结构，只能手动滚动。
2. **有效配置不可见**：imports 展开后的"最终 YAML"、Python 引用解析后的"归一化路径"等中间产物，用户无法直观查看。
3. **Quick Fix 不可浏览**：server 返回的 codeAction 在编辑器里是灯泡，但用户不知道"还有哪些修复命令"可用。

本提案聚焦：**VSCode 扩展的 UI 面板与可视化功能**，让日常使用更高效。

## Goals

- **G1：YAML DSL Explorer（Tree View）**：以树形结构展示当前 DSL 文件的实体层级，支持点击跳转。
- **G2：Virtual Documents / Preview**：提供只读预览视图，展示"有效 YAML"和"解析后的 Python 引用"。
- **G3：Quick Fix 浏览面板**：列出当前文件可用的所有 Quick Fix，可一键执行。
- **G4：DSL 类型指示**：在编辑器内显示当前文件是什么 DSL 类型（demand / workflow）及其 schema 状态。

## Non-Goals

- 不引入新的 LSP 语义能力（实体导航由 c43 负责）。
- 不在 extension 侧解析 YAML 语义（所有数据来自 LSP server 的标准能力或命令）。
- 不做可编辑的 UI（所有面板都是只读展示）。
- 不做 rename / refactor 的 UI（超出本提案范围）。

## Principles

- **语义数据来自 LSP server**：所有 Tree View 节点、Virtual Document 内容、Quick Fix 列表都由 server 提供（通过标准 LSP 能力或 `workspace/executeCommand`）。
- **Extension 不复制规则**：extension 只负责渲染和交互编排，不做任何语义推断。

## Proposal

### 1) YAML DSL Explorer（Tree View）

#### 位置

VSCode 侧边栏，Tab 名称 `ScALIM DSL`。

#### 内容

以 Tree View 展示当前活跃 YAML 文件的 DSL 结构：

```
📦 Sources (3)
├── src_a — loader: csv
├── src_b — loader: ^workflow/book_sheet_rows
└── src_c — loader: excel
📋 Fields (5)
├── field_x — source: src_a, relation: rel_1
├── field_y — source: src_a
└── ...
🔗 Relations (2)
├── rel_1 — steps: 3
└── rel_2 — steps: 1
📤 Outputs (1)
└── out_1
```

#### 交互

- 单击节点 → 跳转到 YAML 文件中对应位置（reveal line）。
- 节点旁可显示 diagnostic 图标（来自 server 的 diagnostics，不是 extension 自己解析）。
- 收起/展开持久化（VSCode 内建支持）。

#### 数据来源

- **方式 A（推荐）**：复用 c43 的 `textDocument/documentSymbol` 返回的 symbols 作为 Tree View 数据源。
- **方式 B（备选）**：如果 documentSymbol 的层级不足以展示详情（如 loader 类型、source 引用），新增一个 server command（例如 `scalim.getDocumentStructure`）返回更丰富的结构化数据。

#### Options & Trade-offs

- 基于 documentSymbol 的方式实现简单且复用 c43，但信息量受限于 SymbolKind 和 SymbolInformation。
- 自定义 command 可以返回任意结构，但增加 server 侧代码。
- 结论：优先用 documentSymbol；如果信息不足再追加 command。

### 2) Virtual Documents / Preview（只读）

#### 预览类型

| 预览类型 | 内容 | 触发方式 |
|---|---|---|
| **Effective YAML** | imports 展开后的最终 YAML（标注每段的来源 fragment） | 命令 `Scalim: Preview Effective YAML` |
| **Resolved Reference** | 当前光标下的 Python 引用归一化后的 module path + 解析链路 | 命令 `Scalim: Resolve Reference` |

#### Effective YAML

1) 命令触发后，打开一个只读 editor tab（URI scheme: `scalim-effective://<path>`）。
2) 内容为 `$import` 全部展开后的 YAML 文本。
3) 每个 import 段用注释标注来源：`# ← from: @/fragments/common.yaml`。
4) 标题栏显示 `(Preview) Generated, read-only`。
5) 数据来源：server command `scalim.getEffectiveYaml` 返回展开后的文本。

#### Resolved Reference

1) 在光标处于某个 Python 引用（如 `module:func`）时触发命令。
2) 打开一个只读 tab，展示：
   - 原始引用字符串
   - 归一化后的 module path
   - 解析链路（来自 c40 的 ResolutionTrace 摘要）
   - 候选 locations 列表（可点击跳转）
3) 数据来源：c40 的 ResolutionTrace。

#### 护栏

- 所有 virtual document 都是只读的（不支持编辑后回写）。
- 不缓存（每次打开都从 server 获取最新数据）。

### 3) Quick Fix 浏览面板

#### 现状

server 返回的 codeAction 在编辑器里显示为灯泡，但用户需要知道"把光标放对位置"才能看到。缺少一个全局入口来浏览当前文件的所有可用修复。

#### Expected Behavior

1) 命令 `Scalim: Show Available Quick Fixes`：
   - 调用 `textDocument/codeAction` 获取当前文件所有 diagnostics 的 codeActions。
   - 在 Quick Pick 中列出，每项显示：
     - 诊断消息（缩写）
     - 修复描述
     - 来源（server）
2) 选择一项后执行对应的 CodeAction（由 server 提供 edit/command）。
3) 如果没有可用 Quick Fix，显示"No quick fixes available for this file"。

#### 数据来源

完全复用标准 `textDocument/codeAction` LSP 请求，不新增 server command。

### 4) DSL 类型指示

#### 位置

YAML 编辑器顶部（breadcrumb 区域下方或 status bar 第二段）。

#### 内容

- 当前文件被判定为 DSL 时，显示类型标签：`Demand DSL` 或 `Workflow DSL`。
- 显示 schema 状态：`Schema: bound` / `Schema: unbound`。
- 当文件被判定为**非 DSL YAML** 时，不显示（避免噪声）；但可通过命令 `Scalim: Explain DSL Status` 查看"为何未激活"。

#### 数据来源

- DSL 类型：server 的 discovery 结果（文件匹配了哪个 schema）。
- Schema 状态：读取 `yaml.schemas` 配置，检查是否有对应绑定。

## Options & Trade-offs

### 1) Tree View 的数据来源

- **documentSymbol（推荐）**：复用 c43 的输出，零额外 server 成本。
- **自定义 command**：更灵活但增加维护面。
- 结论：优先 documentSymbol。

### 2) Virtual Documents 的打开方式

- **只读 editor tab（推荐）**：使用 VSCode 的 `TextDocumentContentProvider` 注册自定义 scheme。
- **Webview Panel**：可以渲染更丰富的 HTML，但实现复杂、性能差。
- 结论：用只读 editor tab。

### 3) Quick Fix 面板的触发频率

- 只在用户显式触发时请求（不自动轮询）。
- 避免频繁调用 `textDocument/codeAction` 影响性能。

## Validation

- **Tree View**：
  - 打开 DSL YAML → Explorer 显示正确的实体层级。
  - 点击节点 → 编辑器跳转到对应行。
  - 打开非 DSL YAML → Explorer 显示空或提示"不适用"。
- **Virtual Documents**：
  - `Preview Effective YAML` → 打开只读 tab，内容为展开后的 YAML + 来源注释。
  - `Resolve Reference`（光标在 Python ref 上）→ 显示归一化路径和解析链路。
- **Quick Fix 面板**：
  - 文件有 diagnostics → Quick Pick 列出可用修复 → 选择执行 → 修复生效。
  - 文件无 diagnostics → 显示"No quick fixes available"。
- **DSL 类型指示**：
  - Demand YAML → 显示 `Demand DSL` + schema 状态。
  - 非 DSL YAML → 不显示。

## Impact（涉及模块）

- VSCode 扩展源码：`extras/vscode-scalim/`
  - Tree View provider
  - TextDocumentContentProvider（virtual documents）
  - Quick Fix 命令
  - DSL 类型状态指示
- 可能涉及 server 侧：
  - `scalim.getEffectiveYaml` command（如果 Effective YAML 预览需要 server 支持 imports 展开）。
- specs（后续转正时）：
  - `openspec/specs/yaml-dsl-vscode-extension/spec.md`
