## 1. Schema 与语法入口升级

- [ ] 1.1 更新 schema 元数据: `output.fields[*]` 支持 string sugar(`field_id` 与 `source.field_id`,二段式)
- [ ] 1.2 更新 schema 元数据: 字段 `relation` 支持 string ref
- [ ] 1.3 更新 schema 元数据: params 支持 `{$runtime: name}` 指令节点,并移除 `$runtime.*` 占位符的 schema 入口
- [ ] 1.4 重新生成并提交 schema 生成物: `just gen-yaml-dsl-editor-schema`

## 2. 语义 validator / parser 实现

- [ ] 2.1 relation 解析升级: `relation: <id>` 解析为对 `relations.<id>` 的引用,并复用既有 chain/step 校验
- [ ] 2.2 output.fields 解析升级: 支持 string 条目(可与对象条目混用),并实现 `field_id` 与 `source.field_id` 的消歧规则
- [ ] 2.3 params 解析升级: 支持 `{$runtime: name}`(单键映射,inline/block 皆可),并在 full validate 阶段拒绝 `$runtime.name` 字符串占位符
- [ ] 2.4 诊断升级: relation steps 的 data_key 误用给出 `field_id` 建议与可复制修复片段

## 3. 迁移与下游盘点

- [ ] 3.1 一步到位迁移仓内 YAML 示例/fixtures/notebooks/skills/frontend examples 到新写法(不保留旧写法分支)
- [ ] 3.2 更新 canonical demo: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml` 使用新写法并保持可运行
- [ ] 3.3 盘点下游适配与同步修改: 读取 `.tmp/known-outer-paths-using-this-package.txt` 并列出需要同步的下游目录(输出/文档中不得引用文件内容)
- [ ] 3.4 新增升级指南(无自动升级器入口,按日期顺序升级): `docs/doc/yaml-dsl/upgrades/2026-03-12-yaml-dsl-micro-tunes.md`,并运行 `just gen-docs` 注入索引

## 4. 测试与验收门禁

- [ ] 4.1 增加/更新 fixtures 覆盖 relation string ref、output.fields string sugar、runtime 指令
- [ ] 4.2 增加/更新单元测试覆盖 schema-only 与 full validate 行为一致性
- [ ] 4.3 通过: `just gen`
- [ ] 4.4 通过: `just qa`
- [ ] 4.5 通过: `just openspec-check`
- [ ] 4.6 归档到: `openspec/changes/archive/YYYY-MM-DD-yaml-dsl-micro-tunes/`
