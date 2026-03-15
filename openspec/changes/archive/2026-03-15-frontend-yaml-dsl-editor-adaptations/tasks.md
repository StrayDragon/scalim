**状态: ✅ 完成**: 已完成 editor 适配与门禁; 5.2 跳过(本机不可做); 5.6 已归档。

## 1. Schema 同步与治理

- [x] 1.1 固化 demand schema 的同步路径: 通过 `just gen-yaml-dsl-editor-schema` 刷新 `frontend/scalim-yaml-dsl-editor/**/schema/demand.gen.json`(不手改)
- [x] 1.2 若引入 workflow schema,补齐前端侧 schema 分发策略(生成/复制/加载)并确保可离线使用
- [x] 1.3 增加一致性门禁: `src/`、`public/`、`dist/` 内置 schema 漂移可被 `just qa`/CI 捕获

## 2. Templates / Getting Started

- [x] 2.1 **BREAKING**: 更新“最小模板”从 `output` 升级为 `outputs`(并与最新 schema validate 对齐)
- [x] 2.2 更新模板/示例覆盖: `imports/$import`、runtime vars 指令节点、`normalize.kind` 新写法等常用片段

## 3. Outline / Visual 适配

- [x] 3.1 outline 支持 `outputs`/`imports` 等新顶层结构,并保持导航定位稳定
- [x] 3.2 可视化面板对 `outputs` 的读写路径闭环(最小集),并保持 patch/preview/roundtrip 规则一致

## 4. 多 schema(可选,用于 workflow YAML)

- [x] 4.1 支持在 editor 中选择 schema(demand/workflow),并让 hover/validate/issue 模型保持一致
- [x] 4.2 若启用 exact(Pyodide)校验,确保其在多 schema 下仍能工作(或明确只支持 demand)

## 5. Docs / QA / Archive

- [x] 5.1 更新 `frontend/scalim-yaml-dsl-editor/README.md`(模板、schema 资源与校验模式说明)
- [x] 5.2 盘点下游适配与同步修改: 跳过(本机不可做); 后续需在其它环境基于 `.tmp/known-outer-paths-using-this-package.txt` 人工处理
- [x] 5.3 通过: `just gen`
- [x] 5.4 通过: `just qa`
- [x] 5.5 通过: `just openspec-check`
- [x] 5.6 归档到: `openspec/changes/archive/2026-03-15-frontend-yaml-dsl-editor-adaptations/`
