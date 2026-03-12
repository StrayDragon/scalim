**Status: DELAYED**: 建议在 `yaml-dsl-micro-tunes` / `yaml-dsl-outputs` / `yaml-dsl-workflow` 等后端语义与 schema 变更稳定后再实现本 tasks,避免重复改动与模板漂移。

## 1. Schema 同步与治理

- [ ] 1.1 固化 demand schema 的同步路径: 通过 `just gen-yaml-dsl-editor-schema` 刷新 `frontend/scalim-yaml-dsl-editor/**/schema/demand.gen.json`(不手改)
- [ ] 1.2 若引入 workflow schema,补齐前端侧 schema 分发策略(生成/复制/加载)并确保可离线使用
- [ ] 1.3 增加一致性门禁: `src/`、`public/`、`dist/` 内置 schema 漂移可被 `just qa`/CI 捕获

## 2. Templates / Getting Started

- [ ] 2.1 **BREAKING**: 更新“最小模板”从 `output` 升级为 `outputs`(并与最新 schema validate 对齐)
- [ ] 2.2 更新模板/示例覆盖: `imports/$import`、runtime vars 指令节点、`normalize.kind` 新写法等常用片段

## 3. Outline / Visual 适配

- [ ] 3.1 outline 支持 `outputs`/`imports` 等新顶层结构,并保持导航定位稳定
- [ ] 3.2 可视化面板对 `outputs` 的读写路径闭环(最小集),并保持 patch/preview/roundtrip 规则一致

## 4. 多 schema(可选,用于 workflow YAML)

- [ ] 4.1 支持在 editor 中选择 schema(demand/workflow),并让 hover/validate/issue 模型保持一致
- [ ] 4.2 若启用 exact(Pyodide)校验,确保其在多 schema 下仍能工作(或明确只支持 demand)

## 5. Docs / QA / Archive

- [ ] 5.1 更新 `frontend/scalim-yaml-dsl-editor/README.md`(模板、schema 资源与校验模式说明)
- [ ] 5.2 盘点下游适配与同步修改: 读取 `.tmp/known-outer-paths-using-this-package.txt` 并列出需要同步的下游目录(输出/文档中不得引用文件内容)
- [ ] 5.3 通过: `just gen`
- [ ] 5.4 通过: `just qa`
- [ ] 5.5 通过: `just openspec-check`
- [ ] 5.6 归档到: `openspec/changes/archive/YYYY-MM-DD-frontend-yaml-dsl-editor-adaptations/`
