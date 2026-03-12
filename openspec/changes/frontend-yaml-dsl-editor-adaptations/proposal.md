## Why

近期 YAML DSL 多项变更正在推进(`imports`、`outputs`、`workflow`、`normalize` 扩展、runtime vars 写法收敛等),但 `frontend/scalim-yaml-dsl-editor/` 仍以旧 schema/旧模板与旧结构(例如 `output`)作为默认作者视角入口,会导致:

- 新语义落地后编辑器提示/模板/可视化面板与 canonical schema 漂移,误导用户并增加迁移成本
- workflow YAML 等新入口无法在编辑器侧获得一致的 schema validate/hover/issue 定位体验

因此需要对前端相关项目做一次集中适配,让编辑器继续作为 YAML DSL 的低摩擦作者入口。

## What Changes

- 同步 schema 与发布物:
  - 将 `src/scalim/dsl/by_yaml/schema/*.gen.json` 的变更稳定同步到 `frontend/scalim-yaml-dsl-editor/**/schema/*.gen.json`(含 `src/`、`public/`、`dist/`)
  - 明确并固化“前端 schema 只来自生成入口”的治理边界(避免手改导致漂移)
- 编辑器模板/起步体验升级:
  - **BREAKING**: “从模板新建(最小模板)”输出从 `output` 升级为 `outputs`(与 repo 一致的一步到位迁移策略对齐)
  - 将常用片段示例纳入模板/示例库(如 `imports/$import`、`normalize.kind` 新写法、runtime vars 指令节点),并确保可被 schema hover/validate 覆盖
- 结构化 UI 与导航适配:
  - 让 outline/面板在结构层面识别新顶层键(如 `outputs`/`imports`)并保持定位/跳转稳定
  - 将与输出相关的可视化编辑从单 `output` 模型迁移到 `outputs` 列表模型(至少保证读/写路径一致,并能生成最小可运行 YAML)
- workflow 作者体验(可选但推荐):
  - 支持在编辑器中选择并应用不同 schema(至少覆盖 demand vs workflow),并让校验/hover/issue 模型在多 schema 下保持一致
  - 若该项变动过大,允许拆分为单独实现阶段,但本 change 先确立 proposal 以锁定范围与约束

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `yaml-dsl-editor-core`: 模板/outline/可视化编辑与校验链路需要适配新的 YAML DSL authoring surface(尤其 `outputs`),并(可选)支持多 schema(workflow)作者体验。

## Impact

- 影响前端项目:
  - `frontend/scalim-yaml-dsl-editor/**`(模板、schema 引用路径、outline/visual 面板、validate worker)
  - 如 workflow schema 需要发布到前端,可能新增/调整 editor 的 schema 资源路径与加载逻辑
- 影响开发/门禁:
  - `just qa`(含前端构建检查)必须在该适配后保持通过
- 不影响 Python 运行时边界(Python 3.6 约束仍由后端实现侧保证)
