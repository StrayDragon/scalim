## 1. `src/scalim`: Mermaid 生成 SSOT（Python 3.6）

- [ ] 1.1 新增 Mermaid 生成模块（输入 `execution_plan/v1` + `execution_deps/v1` + focus 字段集合；输出 `mermaid_text` + 节点映射）
- [ ] 1.2 实现“局部子图裁剪”：以 focus output 的字段为种子，计算上游依赖闭包（含稳定排序与上限保护，避免极端大图）
- [ ] 1.3 Mermaid 输出按 `source_id` 分组为 subgraph（derived/unknown 归入默认组），并保证输出稳定（同输入→同输出）
- [ ] 1.4 为 Mermaid 生成添加单元测试（小型 plan/deps fixture，断言 subgraph 分组 + 边关系 + 稳定性）

## 2. `packages/scalim-yaml-dsl-lsp`: executeCommand 升级（改名 + 新透镜）

- [ ] 2.1 **BREAKING**：移除 `scalim.dumpPlanDeps`，并将其实现升级为 `scalim.dumpDemandSnapshots`（保持原有 plan/deps 快照语义与可诊断错误分支）
- [ ] 2.2 新增 `scalim.dumpDemandLens(uri, opts?)`：组装 outputs 列表（含 `outputs[*].name` 的定位 range）+ focus_output_index + Mermaid（调用 `src/scalim` SSOT 生成器）+ node_anchors
- [ ] 2.3 实现 focus 规则：默认 `focus_output_index=0`；支持 `opts.focus_output_index`；无效 index MUST 降级为 `explain_only`（不得 crash）
- [ ] 2.4 错误/降级分支补齐：非 demand / diagnostics_failed / compile_failed / 读取失败 等场景返回可读结构且不回显 YAML 正文
- [ ] 2.5 为 `dumpDemandSnapshots/dumpDemandLens` 添加测试（至少覆盖：非 demand explain_only、diagnostics_failed、成功返回包含 outputs + mermaid_text + node_anchors）

## 3. `extras/vscode-scalim`: 侧边栏 WebviewView（Workflow / Demand）

- [ ] 3.1 在 `extras/vscode-scalim/package.json` 增加 “可视化透镜”(WebviewView) 贡献点（只做侧边栏 View，不新增 Panel）
- [ ] 3.2 实现 WebviewView host：严格 CSP + nonce；所有资源走 `asWebviewUri`；以 `postMessage` 作为唯一数据通道
- [ ] 3.3 实现 Trusted Workspace gate：`vscode.workspace.isTrusted=false` 时仅展示提示，禁用“生成”与任何 workspace 数据注入
- [ ] 3.4 Workflow 透镜：点击“生成”解析 `workflow.runs[*].demand` 候选列表，并提供“打开 / 打开并生成”
- [ ] 3.5 Demand 透镜：点击“生成”调用 `scalim.dumpDemandLens` 并渲染 outputs 列表 + Mermaid
- [ ] 3.6 Demand 交互：单击输出行只切换 focus（重新请求 `dumpDemandLens`），不跳转；“定位”按钮才 reveal 到 `outputs[*].name`
- [ ] 3.7 Mermaid 交互：支持缩放/平移；默认隐藏 Mermaid 源文本但可复制；点击节点通过 `node_anchors` 跳转到字段定义
- [ ] 3.8 最小验收路径（Extension Host F5）：workflow.yaml → 生成 → 打开并生成 → demand.yaml → outputs/定位/复制/节点跳转可用

## 4. 规范同步与质量门禁

- [ ] 4.1 将本变更 delta specs 同步到主 specs（SSOT=`openspec/changes/c21-vscode-demand-lens/specs/**/*.md`，入口=`openspec sync specs --change c21-vscode-demand-lens`）
- [ ] 4.2 运行 `just openspec-check` 确保 sanitize + validate 通过
- [ ] 4.3 运行 `just qa`（或至少覆盖 Python tests + `pnpm -C extras/vscode-scalim package`）验证无漂移/无明显回归

