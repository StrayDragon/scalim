## 1. Path Constraints (V1 同级目录导入)

- [x] 1.1 校验 `imports.*` 路径仅允许同级文件名(`x.yaml|x.yml` 或 `./x.yaml|./x.yml`),禁止绝对/父目录/子目录/alias 前缀
- [x] 1.2 明确并实现 base_dir 规则: 文件路径入口以 YAML 文件所在目录为 base_dir,递归导入时以片段文件所在目录为 base_dir
- [x] 1.3 设定最大展开深度常量为 20,超过上限 fail-fast(错误包含导入链路)

## 2. Import Expansion Core

- [x] 2.1 定义并实现 `$import` 引用解析(`<alias>(.<path>)*`)与点路径下钻(非 mapping 直接报错)
- [x] 2.2 实现确定性 deep-merge: mapping 递归合并、list replace、类型不匹配报错、本地覆盖导入
- [x] 2.3 支持 `$import` 为 string 或 list 并按顺序合并(后者覆盖前者,最终再被本地覆盖)
- [x] 2.4 支持片段文件递归 `imports/$import` 展开,并实现循环检测与最大深度限制(错误包含导入链路)

## 3. Loader/Validator Integration

- [x] 3.1 在 `YamlDemandLoader.load(yaml_path)` 的 schema/语义校验前插入 import 展开步骤
- [x] 3.2 `YamlDemandLoader.load_string(...)` 与纯文本校验入口若检测到 `imports` 或 `$import` 必须 fail-fast(提示改用文件路径入口)
- [x] 3.3 确保文件路径入口的 schema-only 校验与语义 validator 都基于“展开后的最终配置”运行
- [x] 3.4 更新 CLI 校验命令(`scalim yaml-dsl validate` / `scalim yaml-dsl schema validate`):对文件路径先展开 import 再校验,保证与运行入口一致
- [x] 3.5 更新错误诊断:在异常信息中包含 import 链路与逻辑路径

## 4. Schema & Docs

- [x] 4.1 更新 `schema_dsl` 元数据与生成器,让 JSON Schema 接受顶层 `imports` 与 mapping 内 `$import`
- [x] 4.2 运行 `just gen-yaml-dsl-schema` 并确保 schema 漂移测试通过
- [x] 4.3 运行 `just gen-yaml-dsl-editor-schema` 同步 `frontend/scalim-yaml-dsl-editor/**/schema/demand.gen.json` 与 `dist/` 产物(避免前后端 schema 漂移)
- [x] 4.4 按 SSOT 规则补充 YAML 语法文档与示例,并运行 `just gen-docs`(不手改 `.gen.`)
- [x] 4.5 盘点下游适配与同步修改: 读取 `.tmp/known-outer-paths-using-this-package.txt` 用于盘点与行动(输出/文档中不得引用文件内容)
- [x] 4.6 更新 canonical demo: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml` 覆盖 `imports/$import` 的最小可运行用例
- [x] 4.7 新增升级指南(组级): `docs/doc/yaml-dsl/upgrades/2026-03-13-yaml-reuse-workflow.md`,并运行 `just gen` 注入升级索引

## 5. Tests

- [x] 5.1 单测覆盖:deep-merge 规则、类型不匹配 fail-fast、`$import` 列表顺序、点路径下钻
- [x] 5.2 单测覆盖:循环引用检测与最大深度限制(错误包含链路)
- [x] 5.3 集成测覆盖:import 展开后仍可通过 schema validate 与 full validate,并可成功编译运行
- [x] 5.4 集成测覆盖:同级目录导入路径限制(拒绝 `../`、子目录、绝对路径、alias 前缀)
- [x] 5.5 API 测覆盖:纯文本入口遇到 `imports/$import` fail-fast 的错误提示

## 6. Acceptance / Gates / Archive

- [x] 6.1 通过: `just gen`
- [x] 6.2 通过: `just qa`
- [x] 6.3 通过: `just openspec-check`
- [x] 6.4 归档到: `openspec/changes/archive/YYYY-MM-DD-yaml-dsl-imports/`
