## 1. Schema 与语法入口升级

- [ ] 1.1 更新 schema 元数据: 顶层 `fields` → `derived_fields`
- [ ] 1.2 更新 schema 元数据: `output.fields[*]` 支持 string sugar(`field_id` 与 `source.field_id`)
- [ ] 1.3 更新 schema 元数据: 字段 `relation` 支持 string ref
- [ ] 1.4 更新 schema 元数据: params 支持 `{$runtime: name}` 指令节点,并移除 `$runtime.*` 占位符的 schema 入口
- [ ] 1.5 重新生成并提交 schema 生成物: `just gen-yaml-dsl-editor-schema`

## 2. 语义 validator / parser 实现

- [ ] 2.1 解析入口升级: 读取 `derived_fields` 作为派生字段定义入口(并确保顶层 `fields` fail-fast)
- [ ] 2.2 relation 解析升级: `relation: <id>` 解析为对 `relations.<id>` 的引用,并复用既有 chain/step 校验
- [ ] 2.3 output.fields 解析升级: 支持 string 条目,并实现 `field_id` 与 `source.field_id` 的消歧规则
- [ ] 2.4 params 解析升级: 支持 `{$runtime: name}` 并移除 `$runtime.name` 字符串占位符解析分支
- [ ] 2.5 诊断升级: relation steps 的 data_key 误用给出 `field_id` 建议与可复制修复片段
- [ ] 2.6 盘点其它 alias/解析细节依赖点,并补齐 string ref 兜底(若存在)或明确拒绝策略(写进报错与升级指南)

## 3. 迁移与下游盘点

- [ ] 3.1 一步到位迁移仓内 YAML 示例/fixtures/notebooks/skills/frontend examples 到新写法(不保留旧写法分支)
- [ ] 3.2 盘点下游适配与同步修改: 读取 `.tmp/known-outer-paths-using-this-package.txt` 并列出需要同步的下游目录(输出/文档中不得引用文件内容)
- [ ] 3.3 新增升级指南: `docs/doc/yaml-dsl/upgrades/2026-03-12-yaml-dsl-micro-tunes.md`,并运行 `just gen-docs` 注入索引

## 4. 测试与验收门禁

- [ ] 4.1 增加/更新 fixtures 覆盖 `derived_fields`、relation string ref、output.fields string sugar、runtime 指令
- [ ] 4.2 增加/更新单元测试覆盖 schema-only 与 full validate 行为一致性
- [ ] 4.3 通过: `just gen`
- [ ] 4.4 通过: `just qa`
- [ ] 4.5 通过: `just openspec-check`
