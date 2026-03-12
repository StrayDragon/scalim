## 1. 调研与定案(Review 前置)

- [ ] 1.1 基于 `mvp/current/overview.md` 与 `syntax-catalog.gen.md` 补齐“当前 DSL 痛点清单”(按 root-cause 分组)
- [ ] 1.2 为 plan-a..plan-f 补齐统一的评估矩阵(可读性/一致性/editor 友好/迁移成本/实现风险/长期可扩展性)
- [ ] 1.3 组织 review 并选定一个 canonical plan(其余方案归档为 rejected alternatives)

## 2. 规范层落地(选定方案后)

- [ ] 2.1 创建实施用 change: 将选定 plan 变为唯一 canonical YAML DSL 语法
- [ ] 2.2 更新 OpenSpec specs(按需要拆分成多个 change):
  - `yaml-dsl-schema`
  - `demand-dsl`
  - `source-relations`
  - `field-compute`
  - `yaml-dsl-cli-validation`
  - `yaml-dsl-editor-core`
  - `yaml-dsl-agent-guidance`

## 3. 实现链路(选定方案后;不在本 change 内实现)

- [ ] 3.1 更新 schema meta dataclasses + 生成器输出 `demand.gen.json`
- [ ] 3.2 更新语义 validator: 移除 alias 身份依赖、引入显式 ref 解析、统一错误诊断
- [ ] 3.3 更新 YAML → IR 转换与 runtime compile/run 入口
- [ ] 3.4 更新 CLI: `schema show/path/validate` 与 `validate` 行为一致,并补齐迁移命令(若方案需要)
- [ ] 3.5 更新 editor schema 与补全体验(前端 `public/schema/*.gen.json`)

## 4. 迁移与文档(选定方案后)

- [ ] 4.1 一步到位迁移仓内所有 YAML 示例/fixtures/skills/frontend examples
- [ ] 4.2 更新 canonical demo: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
- [ ] 4.3 增加升级指南: `docs/doc/yaml-dsl/upgrades/YYYY-MM-DD-<group>.md` 并接入自动索引
- [ ] 4.4 更新 skill references 与 docs-site(只保留最新写法;移除旧写法提示)

## 5. 验收门禁

- [ ] 5.1 通过: `just gen`
- [ ] 5.2 通过: `just qa`
- [ ] 5.3 通过: `just openspec-check`
