## Context

现状已有的拼图（代码层面）：

- `frontend/scalim-viz`：适合做深挖与回放（`vizgraph/v1` 静态图 + `vizevent/v1` / trace 事件流），但对 VSCode 用户来说来回切换成本较高。
- 框架侧已实现可视化静态图协议：`ExecutionPlan.to_viz_graph_snapshot()` 生成 `vizgraph/v1`（见 `observability-flow-visualization` 规范）。
- YAML DSL LSP server 已具备静态编译产物导出能力：`scalim.dumpPlanDeps`（demand-only）返回 `execution_plan/v1` + `execution_deps/v1`，但没有用户侧入口，也没有面向“侧边栏透镜”的聚合输出。

本变更要解决的是：在 VSCode 编辑 demand/workflow YAML 的路径上，提供一个**常驻、低干扰、用户触发**的关系透镜；并把 Mermaid 生成下沉到框架侧 SSOT，避免扩展实现漂移。

关键约束：

- **零成本默认**：不点击“生成”不做静态编译/快照/图生成。
- **范围约束**：仅处理“边栏透镜(Workflow)”与“边栏透镜(Demand)”。
- **安全**：Trusted Workspace gate + 严格 CSP；webview 数据只来自 `postMessage`。
- **运行时边界**：`src/scalim/` 代码必须兼容 Python 3.6。

## Goals / Non-Goals

**Goals:**

- 在 VSCode 扩展提供侧边栏 WebviewView：可视化透镜（Workflow / Demand）。
- Demand 透镜在用户点击“生成”后提供：
  - outputs 列表：单击仅切换 focus；提供“定位”按钮跳转到 `outputs[*].name`。
  - Mermaid 局部关系图：按 `source_id` 分组（subgraph），节点可点击并跳转到字段定义处（源字段/派生字段）。
  - Mermaid 源文本默认隐藏，但提供“复制”能力。
- Workflow 透镜在用户点击“生成”后提供：
  - `workflow.runs[*].demand` 候选列表，并提供“打开/打开并生成”。
- LSP server 提供稳定的 executeCommand：
  - `scalim.dumpDemandSnapshots`（重命名自 `dumpPlanDeps`）：导出 demand 静态快照（plan/deps）。
  - `scalim.dumpDemandLens`：导出侧边栏透镜专用 payload（outputs 锚点 + Mermaid + 节点锚点）。
- Mermaid 生成逻辑位于 `src/scalim`（框架侧 SSOT），由 LSP 调用生成，扩展仅渲染与交互。

**Non-Goals:**

- 不在 VSCode 内覆盖 `frontend/scalim-viz` 的时间线/trace/回放能力。
- 不嵌入 scalim-viz bundle，不引入 XYFlow 画布；透镜仅做轻量关系视角。
- 不做自动后台刷新（文档改动后仅提示“需重新生成”）。
- 不新增 Panel（只做侧边栏 View）。

## Decisions

### Decision 1：LSP 命令语义与命名（demand-only snapshots）

**选择：**
- `scalim.dumpPlanDeps` **改名**为 `scalim.dumpDemandSnapshots`（BREAKING）。

**Why：**
- 现实现仅对 demand 生效，“plan/deps”又属于“快照”语义，`dumpDemandSnapshots` 更准确、可长期稳定复用。

**Alternatives：**
- 保留旧名并加 alias：降低外部依赖风险，但本仓库当前无调用方，且会长期遗留歧义。

### Decision 2：新增 `scalim.dumpDemandLens`（透镜专用聚合输出）

**选择：**
- 新增 `scalim.dumpDemandLens(uri, opts?)`，返回“侧边栏透镜一屏所需的数据”：
  - outputs 列表（含定位 range）
  - Mermaid（按 source_id 分组的局部关系图）
  - 节点锚点（node → field definition locations）

**Why：**
- `dumpDemandSnapshots` 保持底层快照语义；透镜 payload 需要额外的聚合信息与锚点映射，不应污染底层快照 contract。

**Alternatives：**
- 让扩展自己基于 snapshots 生成 Mermaid/锚点：实现快，但会造成 drift（用户已明确不希望）。

### Decision 3：Mermaid 生成下沉到 `src/scalim`（SSOT）

**选择：**
- 在 `src/scalim` 提供一个纯函数式的 Mermaid 生成入口（静态、无副作用、Python 3.6 兼容），LSP 调用它。

**输入：**
- `execution_plan/v1` + `execution_deps/v1`（来自 `dumpDemandSnapshots`）
- `focus_field_ids`（来自 outputs 的 effective fields）

**输出：**
- Mermaid 文本（`flowchart`）
- （可选）node 元数据（field_id/source_id/kind）以便上层做点击映射与高亮

**Alternatives：**
- 让 LSP 自己拼 Mermaid：会复制规划层细节；长期更难保证与框架一致。

### Decision 4：锚点跳转以“字段定义处”为主（跨 imports 仍可定位）

**选择：**
- Mermaid 节点点击跳转到字段定义处：
  - 源字段：`main_source.fields.<id>` / `sources.<source_id>.fields.<id>`
  - 派生字段：`fields.<id>`
- LSP 侧优先复用 shared core 现有能力：`build_yaml_dsl_editor_effective_view(...)` 已支持展开 imports 并收集 `field_definitions_by_id`（含 fragment 文件）。

**Why：**
- “定义处”比 “outputs 引用处”稳定；且能跨 `$import` 片段文件定位，符合“直接、正确”的用户预期。

**Alternatives：**
- 仅支持单文件 entity index：实现简单，但 imports 场景下跳转会大量失败。

### Decision 5：outputs 列表交互（选中 focus，不强制跳转）

**选择：**
- outputs 列表：单击行仅切换 focus（更新 Mermaid）；提供“定位”按钮才跳转到 YAML。

**Why：**
- 避免侧边栏“点一下把编辑器带走”，更符合 VSCode 列表选择的直觉。

### Decision 6：用户触发与状态语义（按钮叫“生成”）

**选择：**
- UI 主动作统一命名为 **“生成”**：
  - 首次：生成透镜数据
  - 文档变更后：提示“内容已变更，需要重新生成”

**Why：**
- “同步”容易误导为远端状态对齐；本能力是“静态编译/生成预览”。

### Decision 7：Webview 安全与资源边界

**选择：**
- `vscode.workspace.isTrusted=false` 时禁用生成（透镜只展示说明）。
- Webview 严格 CSP（nonce），禁止远程资源；Mermaid JS 等资源随扩展打包，通过 `asWebviewUri` 引用。
- Webview 不读取 workspace 文件；所有 payload 由扩展侧 `postMessage` 注入。

## Risks / Trade-offs

- **[Risk] imports/模板导致定位缺失** → 透镜用 shared core 的 effective view 做 field definitions；仍失败时给出可读降级提示（“无法定位定义，可能来自动态生成或不在允许范围内”）。
- **[Risk] Mermaid 渲染依赖较大** → 资源随扩展本地打包；仅在用户点击“生成”后渲染；默认隐藏源码文本减少噪声。
- **[Risk] 关系图过大影响可读性** → 透镜仅生成“围绕当前 output 的局部子图”（上游依赖闭包 + 可选深度限制）；按 `source_id` subgraph 分组提升解释性。
- **[Trade-off] 透镜不做时间线** → 明确定位为“编辑期静态关系视角”；深挖/回放仍使用 scalim-viz。

## Migration Plan

- 扩展侧：从调用 `scalim.dumpPlanDeps` 迁移为 `scalim.dumpDemandSnapshots` / `scalim.dumpDemandLens`。
- LSP 侧：实现重命名与新增命令；由于当前无仓内调用方，可直接切换并在文档中标注 BREAKING。
- 回滚：扩展侧降级为仅展示空态说明（不生成透镜数据）；LSP 侧命令保持可诊断错误输出。

## Open Questions

- `dumpDemandLens` 的 options 参数最小集合：是否需要 `cursorPosition`（用于默认聚焦 outputs[*]）与 `maxNodes/maxDepth`（图裁剪）？
> 都需要

- Mermaid 交互基线：是否必须支持平移/缩放/适配视口，或允许先用滚动容器 MVP？
> 必须支持平移/缩放/适配视口
