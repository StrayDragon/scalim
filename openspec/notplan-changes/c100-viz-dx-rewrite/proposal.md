# c100: Viz DX Rewrite (viz-protocol + VSCode-first)

本提案将 `frontend/scalim-viz/` 的能力从“离线回放工具”重排为“开发期 DX 的默认入口”,并引入新能力来解决真实痛点：

- **快速梳理数据流动**：某个 output/字段到底从哪来、经过哪些变换/依赖
- **快速解释触发方式**：为什么某步会跑/不会跑、有哪些控制依赖与条件
- **默认极低成本**：不启用就几乎零开销；启用也以静态预览为默认路径

> 说明：为了便于阅读与讨论，本阶段先落为一个“大提案”。当进入实现阶段再拆为多个 change/PR。

## Why

现有 `scalim-viz` 的“可视化数据链路”主要面向离线回放,核心形态是落盘文件:

- `viz_snapshot.json`: 依赖图快照
- `viz_events.jsonl`: 编排级事件流(JSONL)
- `viz_trace.jsonl`: 高频 trace(JSONL, 可选)
- `viz_schedule_plan.json`: adaptive 计划视角(可选)

这套设计作为“可携带产物/离线回放”可用,但作为“开发期 DX 的默认路径”存在明显问题:

- **默认路径太重**: trace/JSONL 吞吐下写盘与消费都很重；即使 UI 折叠聚合,写盘成本已发生
- **难做到生产零成本**: 一旦“误注册但逻辑上未启用”,热路径仍可能构造 payload
- **不适合 IDE**: VSCode 更适合“命令生成 → 预览展示”的闭环,而不是目录选择器/扫描读取/回放控制
- **不利于分享**: file-based JSONL 很难自然扩展到 HTTP/SSE/WS 的 share 访问

同时,`frontend/scalim-viz/` 现阶段将被冻结(不再新增功能),并作为参考实现保留;直到本提案落地后再讨论移除。

## Principles (Hard Constraints)

### 1) 未启用 = 零成本

- 默认不启用 viz 时:
  - MUST 不注册任何 viz 订阅者/observer
  - MUST 不构造 viz 专属 payload
  - MUST 不产生任何额外 IO/线程/后台任务
- viz 启用必须显式(命令/参数/组件),且可被 IDE 清晰诊断

### 2) 静态预览优先,运行时可选

- **Tier 0 (Static Preview, default)**:
  - 输入: `demand.yaml`
  - 输出: `snapshot + schedule_plan`(静态,无需执行/无需导入用户模块)
  - 目标: 极低成本、生成速度快、适合作为 IDE 默认预览路径
- **Tier 1 (Runtime Stream, later)**:
  - 输出: 低频编排级事件流(不含 trace)
  - transport: 以 stdio/pipe 为主,便于 VSCode 与工具链消费
- **Tier 2 (Debug Trace, last)**:
  - 高频 trace 必须具备采样/背压/按需策略;不得默认全量落盘

### 3) 默认即最新(内测阶段不引入 v* 协议版本)

- 协议以固定 `kind` 识别类型；不引入 `.../v1`、`vizgraph/v*`、`vizevent/v*` 等版本概念
- 如未来出现 breaking change,再单独提出“演进策略”(例如 feature flags / schema_version)；本提案先不提前引入

## The DX: Views & Interaction (核心设计)

### 默认 Focus：围绕 outputs 的因果链

在开发者 DX 上,默认应优先回答“我的 outputs 为什么/怎么来”:

- **默认 Focus=outputs-closure**
  - 高亮 outputs 因果链闭包(依赖闭包)
  - 其它分支 **dim**(可见但弱化),避免误导“图里不存在”
- UI 必须提示当前 focus 策略与隐藏规模(例如 dimmed_nodes/dimmed_edges/hidden_fields 计数),降低认知偏差

#### Focus 输出选择策略(多 outputs 的默认 DX)

从框架用户的直觉出发，“我关心的是某个 output 为什么这样”通常是一条链路的排查,因此建议:

- 如果 demand 只有 1 个 output: 默认聚焦该 output
- 如果 demand 有多个 outputs:
  - UI 提供 output picker(列表/搜索)
  - 默认聚焦 **All outputs 的闭包**(可用但可能较大),并引导用户切到某个 output
  - 当用户选择某个 output 后,将其作为默认(缓存到 workspace state),后续打开同一文件优先复用

> 实现建议：切换 output focus 时优先走 `detail=summary` 的快速再生成,而不是在 webview 侧做复杂推导。

### Progressive Disclosure：同一份静态数据,两种渲染层

你提出的方向非常合理：**局部用 Mermaid**,全量/深挖用 “scalim-viz 模式”(交互式图)。

因此 VSCode 预览提供两类互补视图:

1) **Mermaid View (Local / Focus)**
   - 用途: 快速读懂“这条 output 链路怎么来的”“触发关系怎么连”
   - 形态: 生成 Mermaid(flowchart) 的局部子图(默认 outputs-closure；或基于选中节点的 upstream/downstream closure)
   - 特点: 易读、易复制、易分享(粘到 PR/文档里也能看)
   - 推荐交互:
     - `Copy Mermaid` 一键复制
     - `Open as Markdown`/`Export MD`(便于贴到 issue/PR)

2) **Graph View (Explore / Deep Dive)**
   - 用途: 全量拓扑推演、复杂图布局、字段级细化、Inspector/Plan Lens
   - 形态: 交互式 canvas(参考 `frontend/scalim-viz` 的交互模式,但 IO/协议全面重写)
   - 特点: 可缩放/拖拽/搜索/高亮/布局,适合大图与深挖
   - 推荐交互:
     - `Explore` 切换为全量拓扑(取消 dim),用于静态推演
     - `Load Full Detail` 触发二次 Sync,解锁字段级解释/Inspector 深挖
     - `Layout (Focus)` 默认可用且快速(仅对当前 focus 子图做布局)
     - `Layout (All)` 作为显式操作(避免大图自动布局卡顿);可在后台(worker)执行

> 关键点：Mermaid 不取代 Graph。Mermaid 解决“快速理解/分享”,Graph 解决“复杂推演/深挖解释”。

### Sync 策略：手动优先,自动可选

- 默认仅 **手动 Sync**(不注册 watcher)
- 可选 `Auto Refresh`(默认关闭): 仅在用户显式开启且 webview 已打开时,保存 YAML 触发重新生成与刷新
- Graph View 的全量布局/渲染可采用 lazy render(例如分组折叠/按需展开)避免大图卡顿

## viz-protocol (transport-first, UI 可复用)

定义一个可被 webview / CLI / future HTTP share 共用的消息协议(“同一 UI,不同 transport”)。

### Envelope

- `kind`: `scalim.viz.envelope` (常量字符串)
- `type`: `bundle | events_chunk | status | error`
- `payload`: 负载

### Bundle (Tier0 主形态)

- 静态预览默认输出单条 `bundle`(JSON):
  - `payload.snapshot`：结构图快照(用于 Mermaid/Graph 两类视图)
  - `payload.schedule_plan`：可选计划视角(Plan Lens)
  - `payload.meta`：created_at、source、generator、以及渲染/聚焦提示

### Detail Levels: 默认粗粒度,深挖二次 Sync (full-detail)

为满足“默认快/轻”与“深挖可解释”的矛盾,静态预览的 `bundle` 需要支持 **detail level**:

- **默认(detail=summary)**:
  - 仅包含“足够画 Mermaid + 粗粒度 Graph”的信息
  - 数据流展示只到“字段名集合”粒度:
    - `a,b,c -> x,y` (仅字段名集合；不展示 mapping 表达式/函数/逐字段 lineage)
  - 字段集合在 UI 上的默认呈现遵循“Focus 优先 + inline budget”:
    - 优先显示与当前 Focus(例如 outputs-closure)相关的字段名
    - 不同视图使用不同的 inline budget(避免 Mermaid 图被长 label 污染):
      - Mermaid View: 每侧最多显示 3 个 focus 字段
      - Graph View: 每侧最多显示 6 个 focus 字段
    - 默认 label 规则(示例):
      - `a,b,c …(+4 focus) (+12 other) -> x,y …(+1 focus)`
      - 其中 `…(+N focus)` 表示“还有 N 个 focus 字段未展示”,`(+M other)` 表示“其它字段数量”
  - 不携带字段级 lineage 的全量细节(避免 bundle 体积与生成成本爆炸)
  - Focus/Explore 的拓扑与 data/control 边必须完整可用
- **深挖(detail=full)**:
  - 由用户显式触发二次 Sync 生成(例如 “Sync (Full Detail)” 或进入 Deep Dive 时加载)
  - 携带字段级 lineage/映射/解释所需的更细数据,用于 Inspector 与字段级排障

建议 `payload.meta.detail = summary|full` 作为 UI 可见状态,并在从 `summary` 切换到 `full` 时保留相同的 node/edge ids,以便 UI 在同一画布中无缝升级数据。

#### “Focus 相关字段”的推荐定义(可实现且有解释力)

从 DX 角度,“Focus 相关字段”不能靠 UI 猜,否则会误导。建议由编译器在静态阶段提供:

- 在 `detail=summary` 下,对每条 `data` 边提供字段集合摘要(建议 shape,便于 UI 稳定呈现):
  - `fields_from.focus_sample`: focus 字段名样本(列表,最多 6 个)
  - `fields_from.focus_total`: focus 字段总数
  - `fields_from.other_total`: 其它字段总数
  - `fields_to.focus_sample`: 同上
  - `fields_to.focus_total`: 同上
  - `fields_to.other_total`: 同上
- focus 字段的语义:
  - 以当前 focus outputs 为目标,做一次字段“需求回传”(类似 liveness/required-fields 分析)
  - 仅将对当前 focus outputs **确实有贡献**的字段纳入 focus 字段集合(体现在 `focus_total` 与 `focus_sample`)
  - `focus_sample` 的顺序必须稳定且可复现(推荐按字段名规范化后的字典序),以便:
    - 同一份 YAML 多次生成不抖动
    - `summary -> full` 升级时 UI 不漂移

UI label 的计数规则(推荐):

- 展示侧 focus 字段数量 `shown = min(inline_budget, len(focus_sample))`
- `hidden_focus = max(0, focus_total - shown)` → 显示为 `…(+{hidden_focus} focus)`
- `other_total > 0` → 显示为 `(+{other_total} other)`

这样 UI 才能做到:

- 默认展示“最有用的字段名集合”
- 其余字段折叠为 `(+N)` 而不损失正确性

### Snapshot: 必须直接服务“数据流 + 触发解释”

快照必须显式区分两类关系(否则很难解释“为什么会触发/不触发”):

- `edge.kind = data`：数据依赖/数据流动(字段/输出的来源链)
- `edge.kind = control`：触发/控制依赖(条件/顺序/门控)

建议每个 node/edge 都携带可定位信息(强烈建议)：

- `source`：YAML path / 原始 key / 可选 file:line:col, 以支持 “Go to YAML” 与诊断回链
- `id`：必须稳定且可复现(建议派生自 YAML path/IR identity),以支持:
  - `summary -> full` 的无缝升级
  - UI 侧缓存/对比(diff)/定位不漂移

> Mermaid View 可将 `data`/`control` 用不同线型/颜色表示(例如 `-->` vs `-.->`)；Graph View 也同理。

## Components (生成链路与集成点)

### A) Framework: 静态预览编译入口 (demand-only)

新增一个“预览编译入口”(public API),用于 demand YAML 的纯静态链路:

- MUST 仅依赖 YAML -> config -> IR -> plan 的静态编译
- MUST NOT import 用户模块
- MUST NOT resolve runtime bindings
- MUST 保持 `src/scalim/` Python 3.6 兼容

产出:

- `snapshot`
- `schedule_plan`(可选)
- `meta`

### B) CLI: `scalim-cli viz snapshot <demand.yaml>`

将生成能力放在 `scalim-cli` 的好处:

- CLI 本身 `>=3.10`,适合承载工具体验(参数/诊断/输出格式)
- VSCode extension 只需调用命令并解析输出,无需在 extension host 内复刻编译逻辑
- 用户不执行命令就没有额外开销(符合“未启用=零成本”)

输出建议:

- stdout 输出单个 JSON envelope(`bundle`)
- 默认 stderr 人类可读；可选 `--format=json` 将错误也包装成 envelope 便于 IDE 展示

推荐参数(面向 DX 与可预期性):

- `--detail=summary|full`:
  - 默认 `summary`
  - `full` 仅在用户显式触发 Deep Dive/Full Detail 时使用
- `--focus-output <name>`:
  - 用于多 outputs demand 的“聚焦某个 output 链路”
  - VSCode output picker 可直接驱动该参数(切换时再生成,同时可做缓存)
- `--pretty`(可选): 仅用于人类阅读,IDE 默认不使用

可选增强(不作为默认硬要求):

- `--emit=mermaid|md`：直接输出 Mermaid/Markdown 便于在终端/文档中使用

### C) VSCode Extension: Webview-first 预览体验

在 `extras/vscode-scalim` 引入 Viz Preview:

- 命令:
  - `Scalim: Viz Preview (Demand)`：生成并打开/刷新预览(也是手动 Sync)
- activation:
  - 扩展已因 YAML LSP 使用 `onLanguage:yaml` 激活;因此 viz 模块必须动态 import/lazy init
  - 禁止在 activate 阶段扫描目录/注册 watcher/启动后台服务
- 安全:
  - Trusted Workspace gate：非受信任工作区默认不执行外部命令
  - webview 严格 CSP；所有数据通过 `postMessage` 注入

Webview UI 建议结构:

- 顶部状态栏: yaml 路径、生成时间、生成器信息、状态/错误、Sync/Auto Refresh
- Tab/Mode:
  - `Mermaid`(默认 Focus)：快速理解/复制/分享
  - `Graph`(Explore/Deep Dive)：全量/深挖/布局/Inspector
- 侧栏(后续逐步补齐): Inspector / Plan Lens

推荐的“显式成本”触发点:

- `Sync` 默认只拉取 `detail=summary`
- `Load Full Detail`/`Sync (Full Detail)` 明确触发二次生成(`detail=full`)
- 进入 Graph/Explore 不应隐式触发 full-detail(避免用户不知不觉付出成本)

## Tier1 Runtime Stream (later, 推荐最小集合)

静态预览(Tier0)覆盖“结构理解/静态推演”的主需求；运行时(Tier1)只解决两类 DX 痛点:

- “我跑起来了,现在进度/错误/关键节点状态是什么”
- “为什么某步没有触发/为什么跳过(需要最小证据链)”

因此 Tier1 必须克制,避免退化为旧 JSONL/trace 的重链路。

### 最小事件集(建议)

- `run_started` / `run_finished`
- `node_started` / `node_finished`(status + duration + optional summary)
- `loader_called`(summary: cache hit/miss + key + duration;禁止高频逐字段 dump)
- `output_emitted`(summary)
- `diagnostic`(warning/error,带 source 定位)
- `stats`(可选): dropped_count / queue_depth 等背压指标

### 性能与可靠性要求

- MUST 非阻塞: 不得在热路径等待 IO/网络
- MUST 有界内存: 明确背压与丢弃策略,并通过 `stats` 可诊断
- MUST “未启用=零成本”: 不注册订阅者/不构造 payload

### transport 建议

- IDE/CLI: NDJSON/stdout(每行一个 envelope)
- Share(未来): SSE/WS 复用同一 envelope

## Share (HTTP) 预留 (later)

未来若需要 share,建议形态:

- 由 VSCode 命令显式启动 server(默认只读)
- 使用随机 token + 限制可访问范围(禁止任意文件读取/路径穿越)
- Remote 场景通过 `vscode.env.asExternalUri`/端口转发获取可访问 URL

协议层面要求:

- 同一套 `viz-protocol` envelope 可走 stdio 或 HTTP/SSE/WS
- UI 尽量做到“同一渲染器,不同 transport”

## Migration Strategy

- `frontend/scalim-viz/` 冻结为参考实现(不再新增功能)
- 新链路以 VSCode/CLI 为默认入口
- 当本提案落地并覆盖关键 DX 场景后,再单独提案移除旧前端(不在本提案内)

## Checklist (legacy scalim-viz capabilities)

用于对照旧能力,逐项决定“需要/不需要/以后再说”(不意味着全部实现)。

### Data/Replay
- 目录导入与多 run 切换
- workflow bundle + drill-down (本提案阶段先 demand-only)
- events-only vs trace + trace 过滤/折叠 (运行时后置)
- 事件 run_id 过滤(同文件包含多个 run_id)

### Views
- Graph(canvas): nodes/edges + 选中/高亮/整理节点/还原视角 + 全量布局
- Mermaid(local): outputs closure / node closure 的局部视图 + 复制/分享
- Timeline/Replay: 回放控制(后置到运行时 Tier1/Tier2)
- Inspector: 节点/边摘要 + 触发解释 + 大字段查看(按需展开)
- Plan Lens: schedule plan 视角 + 与 graph 联动(后续逐步补齐)

### Live/DX
- 一键生成并打开预览(IDE 命令)
- follow/tail 增量更新(后置：先把静态体验做成默认路径)

### Share/Export
- export 便携包(离线分享)
- HTTP share(未来)

## Dependencies / Related Specs

后续实现可能需要扩展/新增以下 SSOT:

- 现有: `openspec/specs/flow-visualization/spec.md`
- 现有: `openspec/specs/observer-concurrency-contract/spec.md`
- 建议新增: `openspec/specs/viz-protocol/spec.md`
- 相关: `openspec/specs/yaml-dsl-observability-boundary/spec.md` (运行时 knobs 的边界)

## Risks / Open Questions

- 静态 snapshot 的字段粒度如何选择:
  - Mermaid View 需要的最小信息 vs Graph Deep Dive 需要的细节
  - `summary` 与 `full` 的边界如何定义,以及如何在 UI 上明确呈现差异避免误解
  - `summary` 中字段集合过大时的呈现策略(与 Focus 相关的字段优先显示,其它折叠计数)
- 大图渲染性能:
  - Explore 全量拓扑的布局与交互如何保证不卡顿(折叠/分组/lazy layout)
- 运行时事件集(Tier1)最小集合如何定义,以及对性能/可解释性的权衡
