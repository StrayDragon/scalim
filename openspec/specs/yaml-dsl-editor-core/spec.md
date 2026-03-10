# yaml-dsl-editor-core Specification

**状态: ✅ 已实现**
## Purpose
定义 YAML DSL 编辑器的核心能力:文本优先编辑、Visual 双向同步、统一校验模型、roundtrip 稳定性与可选 exact(Pyodide)语义校验.

## Related Code (as implemented)
- `frontend/scalim-yaml-dsl-editor/src/app/AppShell.svelte`
- `frontend/scalim-yaml-dsl-editor/src/ui/editor/YamlEditor.svelte`
- `frontend/scalim-yaml-dsl-editor/src/ui/editor/yaml_lsp.worker.ts`
- `frontend/scalim-yaml-dsl-editor/src/schema/demand.gen.json`
- `frontend/scalim-yaml-dsl-editor/src/ui/panels/VisualPanel.svelte`
- `frontend/scalim-yaml-dsl-editor/src/ui/components/SchemaHint.svelte`
- `frontend/scalim-yaml-dsl-editor/src/ui/panels/IssuesPanel.svelte`
- `frontend/scalim-yaml-dsl-editor/src/services/semantic_validate.ts`
- `frontend/scalim-yaml-dsl-editor/src/services/pyodide_validate.worker.ts`
- `frontend/scalim-yaml-dsl-editor/src/services/yaml_patch.ts`
- `frontend/scalim-yaml-dsl-editor/src/ui/overlays/PatchPreviewModal.svelte`
## Requirements
### Requirement: 作为纯前端应用运行

系统 MUST 提供一个可在本仓库内开发与构建的前端应用 `frontend/scalim-yaml-dsl-editor/`,其基础能力不依赖 Python 环境即可使用(仅通过浏览器与本地文件交互).

#### Scenario: 开发与构建
- **WHEN** 开发者在 `frontend/scalim-yaml-dsl-editor/` 安装依赖并运行开发命令
- **THEN** 系统提供可热更新的本地开发服务
- **THEN** 系统提供构建命令输出静态资源(可部署到任意静态站点)

### Requirement: 文本编辑为主路径(Text-first)

系统 MUST 提供 YAML 文本编辑能力作为主交互路径,用户可以直接编辑 YAML 内容,并实时获得与 YAML DSL schema 一致的提示与校验结果.

#### Scenario: 直接编辑 YAML
- **WHEN** 用户在编辑器中修改 YAML 文本(例如修改 `main_source.loader`)
- **THEN** 系统保持文本内容为单一事实来源(single source of truth)
- **THEN** 系统更新补全/hover/校验与诊断面板展示

### Requirement: 可视化与 YAML 双向编辑(Split)

系统 MUST 提供可视化结构化编辑能力,并与 YAML 文本编辑保持双向同步:可视化 UI 的修改应实时反映到 YAML;用户直接编辑 YAML 时,可视化 UI 应基于解析结果刷新显示.

#### Scenario: Visual 修改实时体现在 YAML
- **WHEN** 用户在可视化 UI 中修改某个字段(例如 `output.path`)
- **THEN** YAML 文本应实时更新为等价变更

#### Scenario: YAML 修改刷新 Visual
- **WHEN** 用户在 YAML 中新增/删除一个可视化面板可表达的字段
- **THEN** 可视化 UI 应刷新并反映新增/删除结果

### Requirement: 使用 canonical JSON Schema 提供补全与 hover

系统 MUST 以 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json` 作为唯一 canonical schema 输入,为 YAML 提供 schema 级别的补全、hover(markdownDescription)与基础校验.

#### Scenario: schema 驱动的 hover
- **WHEN** 用户将光标移动到 `relations.*.steps.from` 或 `sources.*.params` 等字段
- **THEN** 系统展示来自 schema 的字段说明(含 markdownDescription 与示例)

### Requirement: editor exposes `extract` with the same semantics as the canonical schema
系统 MUST 基于 canonical schema 在编辑器中暴露 `extract` 的补全、hover 与 schema-only 校验,并保持前端文案与主仓库 schema 一致。

#### Scenario: hover 展示 `extract` 的 current-row-relative 解释
- **WHEN** 用户在 `sources.*.fields.*.extract` 或 `main_source.fields.*.extract` 上查看 hover
- **THEN** 编辑器 MUST 展示“相对当前 row value 解析”的说明
- **AND** MUST 展示 `CustomerMark.clearn_reason_level` / `\"[1].x\"` / `'[\"a.b\"]'` 之类的最小示例(明确为字符串,避免 YAML 歧义)

### Requirement: 导入/导出与模板新建

系统 MUST 支持从本地导入 YAML 文件、将当前编辑内容导出为 YAML 文件,并提供“从模板新建”的起步体验(最小可运行配置 + 常见完整示例骨架).

#### Scenario: 从模板新建
- **WHEN** 用户选择“新建(最小模板)”
- **THEN** 系统生成包含 `name`、`main_source` 与 `output` 的最小 YAML
- **THEN** 系统将模板内容载入编辑器并可立即进行补全与校验

### Requirement: Outline 与快速导航

系统 MUST 提供对 YAML DSL 结构的 outline(例如:top-level、main_source、sources、relations、fields、output、observability、guardrails),并支持点击导航到对应 YAML 文本位置.

#### Scenario: 通过 outline 跳转
- **WHEN** 用户在 outline 中点击 `sources.customers.fields`
- **THEN** 系统将光标/视图定位到 YAML 中对应的块位置

### Requirement: 可视化辅助视图(关系与依赖)

系统 MUST 提供可视化辅助视图以提升理解与编辑效率,包括但不限于:
- sources/relations 的关系图(source 节点 + steps 边)
- derived fields 的依赖图(字段拓扑/缺失依赖提示)

#### Scenario: 关系图可用于理解与定位
- **WHEN** 用户打开关系图视图
- **THEN** 系统展示从 `main_source` 到各个 `sources` 的 relation steps 链路摘要
- **THEN** 用户点击图中节点/边时,系统可以导航到对应 YAML 位置

### Requirement: 统一 issue 数据模型与定位能力
系统 MUST 将校验输出统一为 issue 列表,至少包含 `severity`、`message`、`path`、`source`,并尽可能提供 `line/column` 与 `suggestions`.
Issue 模型 MUST 可直接用于面板展示与跳转定位.

#### Scenario: issue 点击可定位
- **WHEN** 用户在 issues 面板点击某条错误
- **THEN** 编辑器可基于 `line/column` 或 `path` 跳转到对应 YAML 位置

### Requirement: 默认提供 schema-only 校验并支持 strict
系统 MUST 默认提供 schema-only 校验能力.
系统 MUST 支持 strict 模式,将未知字段等诊断提升为 error 以用于提交前收敛.

#### Scenario: strict 下未知字段失败
- **WHEN** 用户启用 strict 并输入未知字段
- **THEN** 系统 MUST 以 error 报告该问题

### Requirement: 支持 local semantic 与 exact semantic 并合并展示
系统 MUST 支持可选语义校验链路(local semantic / exact semantic),并与 schema issues 合并展示且保留来源.

#### Scenario: 语义错误可见
- **WHEN** relation steps 断链或 legacy bind/to_bind 使用/params 模板指令语义错误
- **THEN** 系统 MUST 展示 semantic issue 并可定位

### Requirement: exact semantic 基于 Worker + Pyodide 且默认关闭
exact semantic MUST 作为显式启用能力,默认不依赖 Pyodide.
exact 校验 MUST 在 WebWorker 中运行,避免阻塞主线程.
exact 执行边界 MUST 使用 `validate_yaml_text_json(...)`(或等价稳定 API)返回结构化 JSON issues.

#### Scenario: 未启用 exact 仍可工作
- **WHEN** 用户不启用 exact
- **THEN** 编辑器仍提供 schema 与 local semantic 校验

### Requirement: exact 初始化失败自动降级
当 Pyodide 资源不可用、wheel 安装失败或网络受限时,系统 MUST 自动降级到 local semantic 并展示失败原因,不影响编辑主流程.

#### Scenario: Pyodide 不可用自动降级
- **WHEN** exact 初始化失败
- **THEN** 编辑器继续可用并回退到 local semantic

### Requirement: exact 依赖最小化
浏览器侧 exact 安装 MUST 避免隐式拉取重依赖(如 `numpy/pandas/openpyxl`);wheel 安装路径应使用 `deps=False` 或等价策略确保轻量.

#### Scenario: exact 不拉取重依赖
- **WHEN** 在 Pyodide 中安装 PROJECT_DIST_NAME wheel
- **THEN** 不应触发 `numpy/pandas/openpyxl` 下载或 import

### Requirement: roundtrip 优先补丁并尽量保留格式
结构化编辑 MUST 采用补丁优先策略,尽量保留原 YAML 注释、排版、anchors/aliases.
仅在无法安全补丁时允许大范围重写.

#### Scenario: 标量修改不重写全文
- **WHEN** 用户仅修改 `name` 或 `output.path`
- **THEN** 系统 SHOULD 仅应用局部补丁并保留注释/排版

### Requirement: 重写前必须 diff 预览并显式确认
当修改不可避免触发全量或大范围重写时,系统 MUST 展示 diff 预览并要求用户确认;取消后 MUST 保持原文不变.

#### Scenario: 复杂结构触发确认
- **WHEN** 修改涉及 merge/alias 边界导致无法安全补丁
- **THEN** 系统先展示 diff,确认后才应用

### Requirement: alias 编辑提供共享与拆分策略
编辑 alias 引用对象时,系统 MUST 提供“编辑共享模板”与“拆分为实例”两种明确策略,并据用户选择生成变更.

#### Scenario: alias 编辑弹出策略选择
- **WHEN** 用户编辑来自 `*alias` 的结构对象
- **THEN** 系统提示共享编辑或拆分实例,并按选择应用

### Requirement: 可视化编辑块必须提供稳定可发现的新增入口
系统 MUST 在字段/关系等可重复结构的编辑块中提供稳定、可预测的新增入口(包括但不限于 `main_source.fields`、`sources.*.fields`、`relations.*.steps`、`fields` 与 params 编辑区).
新增入口 MUST 使用统一的加号图标按钮样式,并通过 `title`/`aria-label` 提供对象语义(如字段/step/relation/source),不得让用户在不同块中重新学习入口形态.

#### Scenario: 用户在不同编辑块中切换后仍能找到新增入口
- **WHEN** 用户从 `main_source.fields` 切换到 `sources.*.fields` 或 `relations.*.steps` 继续编辑
- **THEN** 每个块都 MUST 展示同类位置与同类语义的新增入口
- **THEN** 用户不需要依赖猜测或阅读实现细节即可完成“继续新增”操作

#### Scenario: 新增入口语义由提示与可访问属性承载
- **WHEN** 用户查看任一块的新增按钮
- **THEN** 按钮样式 MUST 为统一加号图标形态
- **THEN** 按钮 MUST 通过 `title`/`aria-label` 明确对应对象类型(字段/step/relation/source 等)

### Requirement: 同一编辑器中的可操作项必须采用一致的交互视觉体系
系统 MUST 对编辑器内按钮与交互控件使用统一的视觉层级、尺寸与状态反馈(default/hover/focus/disabled),避免同级动作在不同面板中出现割裂样式.
系统 MUST 保证新增、删除、移除、跳转等关键操作在各面板具有一致的操作反馈与可辨识性.

#### Scenario: 同级主动作具有一致样式
- **WHEN** 用户在 Sources、Relations、Derived Fields、Main Source Fields、Source Fields 面板查看主新增动作
- **THEN** 主新增动作 MUST 呈现一致的按钮风格与交互状态

#### Scenario: 关键动作在键盘导航下具有一致焦点反馈
- **WHEN** 用户使用键盘 Tab 导航到任一关键按钮
- **THEN** 按钮 MUST 展示可见且一致的 focus 状态

### Requirement: 关键操作的可见性不得依赖 hover-only
系统 MUST 确保关键操作(如删除/移除/清空)在无 hover 场景下仍可发现与触达,以支持触屏设备、键盘导航与新手学习路径.
hover 效果 MAY 作为增强,但 MUST NOT 是关键操作的唯一可见方式.

#### Scenario: 触屏环境仍可发现关键操作
- **WHEN** 用户在不支持 hover 的触屏环境中使用编辑器
- **THEN** 关键操作 MUST 保持可见或可直接触达
- **THEN** 用户能够完成删除/移除等动作而不依赖鼠标悬停

#### Scenario: 鼠标环境中 hover 仅增强可见性
- **WHEN** 用户在桌面环境悬停可编辑项
- **THEN** 系统可以增强关键按钮视觉反馈
- **THEN** 即使不悬停,关键按钮也 MUST 保持可发现

### Requirement: editor exposes source-level `normalize` with canonical schema guidance
系统 MUST 基于 canonical schema 在编辑器中暴露 `sources.*.normalize` 的补全、hover 与 schema-only 校验,并清楚区分它与字段级 `extract` 的边界。

#### Scenario: hover 说明 `normalize` 与 `extract` 的边界
- **WHEN** 用户在 `sources.*.normalize` 上查看 hover
- **THEN** 编辑器 MUST 展示其 source-level whole-result 语义
- **AND** MUST 提示字段内部取值应使用字段级 `extract`

## Notes
- `yaml-dsl-editor-cli-bridge` 历史方案已移除;exact 语义校验以 Pyodide 方案为准.
