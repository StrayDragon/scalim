## Why

当前 `frontend/scalim-viz` 适合做深挖（静态图 + 运行态事件/trace 时间线回放），但对 VSCode 用户而言，“改 YAML → 切到另一个工具看关系 → 再切回编辑器”的成本偏高，尤其是在 `outputs` / 关联链 / 派生字段迭代阶段。

另一方面，LSP 侧已经具备“静态关系”能力（plan/deps 快照），但缺少一个面向编辑路径的、可点击跳转的轻量透镜输出；同时 `scalim.dumpPlanDeps` 的命名与其语义不匹配（仅对 demand 生效的静态快照），不利于长期作为稳定接口被复用。

## What Changes

- 新增 VSCode 侧边栏常驻 WebviewView：**可视化透镜（Workflow / Demand）**，用于在编辑 YAML 时以“锚点列表 + 局部关系图”快速理解依赖关系，减少上下文切换。
  - 交互以用户触发为主：默认不计算；用户点击 **“生成”** 后才编译/生成透镜数据。
  - 仅覆盖两种透镜：
    - Workflow：点击“生成”后解析 `workflow.runs[*].demand` 并提供打开/打开并生成入口。
    - Demand：点击“生成”后展示 outputs 列表（单击只切换 focus，不跳转；提供“定位”按钮）与 Mermaid 局部关系图；Mermaid 源文本默认隐藏但可复制。
- **BREAKING**：重命名 LSP `workspace/executeCommand`：
  - `scalim.dumpPlanDeps` → `scalim.dumpDemandSnapshots`（更准确表达“仅对 demand 导出静态快照”）。
- 新增 LSP `workspace/executeCommand`：
  - `scalim.dumpDemandLens`：面向侧边栏透镜的专用 payload（outputs 锚点 + Mermaid + 节点锚点映射等）。
- 将 Mermaid 生成逻辑下沉到 `src/scalim`（框架侧 SSOT），避免在 VSCode 扩展内复刻依赖裁剪与分组规则导致漂移；并支持按 `source_id` 分组（subgraph）以提升可解释性。
- 明确边界：侧边栏透镜仅提供**静态关系视角**；`frontend/scalim-viz` 仍负责运行态事件/trace 时间线与回放体验，本变更不尝试覆盖或替代。

## Capabilities

### New Capabilities
- `tools-vscode-demand-lens`: VSCode 侧边栏常驻的 Demand/Workflow 透镜（WebviewView），以懒加载“锚点 + Mermaid 局部关系图”辅助 YAML 编写。

### Modified Capabilities
- `yaml-dsl-lsp-server`: 扩展 `workspace/executeCommand` contract（新增 `scalim.dumpDemandLens`；将 `scalim.dumpPlanDeps` 更名为 `scalim.dumpDemandSnapshots` 并明确其 demand-only 语义）。

## Impact

- 代码影响范围：
  - `packages/scalim-yaml-dsl-lsp/`：新增/调整 executeCommand，透镜 payload 组装与降级错误输出。
  - `src/scalim/`：新增 Mermaid 生成与局部子图裁剪 SSOT（需保持 Python 3.6 兼容）。
  - `extras/vscode-scalim/`：新增侧边栏 WebviewView + 消息协议 + “生成/定位/复制”交互（严格 CSP + Trusted Workspace gate）。
- 兼容性：
  - 任何外部 client 若调用旧命令 `scalim.dumpPlanDeps` 将受影响（预期影响面极小；本仓库当前无调用方）。
- 安全与隐私：
  - Webview 不读取工作区文件内容作为数据通道；所有透镜数据由扩展侧 `postMessage` 注入。
  - 非受信任工作区默认禁用透镜数据生成并提供可读提示。
