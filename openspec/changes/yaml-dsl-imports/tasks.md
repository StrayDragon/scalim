## 1. Public API & Path Resolution

- [ ] 1.1 为 `scalim.dsl.by_yaml.run()` / `compile()` 增加可选参数 `path_aliases`
- [ ] 1.2 扩展 `RunOptions` 以承载 `path_aliases`,并确保默认值不改变现有行为
- [ ] 1.3 实现路径解析工具:支持绝对/相对路径与 `"@/..."`、`"ALIAS:/..."` 前缀展开(缺失 alias fail-fast)

## 2. Import Expansion Core

- [ ] 2.1 定义并实现 `$import` 引用解析(`<alias>(.<path>)*`)与点路径下钻(非 mapping 直接报错)
- [ ] 2.2 实现确定性 deep-merge: mapping 递归合并、list replace、类型不匹配报错、本地覆盖导入
- [ ] 2.3 支持 `$import` 为 string 或 list 并按顺序合并(后者覆盖前者,最终再被本地覆盖)
- [ ] 2.4 支持片段文件递归 `imports/$import` 展开,并实现循环检测与最大深度限制(错误包含导入链路)

## 3. Loader/Validator Integration

- [ ] 3.1 在 `YamlDemandLoader.load/load_string` 的 schema/语义校验前插入 import 展开步骤
- [ ] 3.2 确保 schema-only 校验与语义 validator 都基于“展开后的最终配置”运行
- [ ] 3.3 更新错误诊断:在异常信息中包含 import 链路与逻辑路径

## 4. Schema & Docs

- [ ] 4.1 更新 `schema_dsl` 元数据与生成器,让 JSON Schema 接受顶层 `imports` 与 mapping 内 `$import`
- [ ] 4.2 运行 `just gen-yaml-dsl-schema` 并确保 schema 漂移测试通过
- [ ] 4.3 按 SSOT 规则补充 YAML 语法文档与示例,并运行 `just gen-docs`(不手改 `.gen.`)

## 5. Tests

- [ ] 5.1 单测覆盖:deep-merge 规则、类型不匹配 fail-fast、`$import` 列表顺序、点路径下钻
- [ ] 5.2 单测覆盖:循环引用检测与最大深度限制(错误包含链路)
- [ ] 5.3 集成测覆盖:import 展开后仍可通过 schema validate 与 full validate,并可成功编译运行
- [ ] 5.4 API 测覆盖:`path_aliases` 对 `imports` 路径与相对路径解析的影响(含 `"@/..."` 需字符串形式的用例)

