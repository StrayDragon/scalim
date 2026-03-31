## 1. Schema & config parsing

- [ ] 1.1 移除 `outputs_defaults` 数据模型与 schema DSL 定义(含 keys/constants),并确保 schema-only 校验不再接受该字段
- [ ] 1.2 更新 demand loader/parser: 不再解析 `outputs_defaults`,并对 Excel outputs 要求显式 `outputs[*].to.book`
- [ ] 1.3 生成并校验 schema 生成物漂移: SSOT=`src/scalim/dsl/by_yaml/schema_dsl/**`; 生成入口=`just gen-yaml-dsl-schema`; 验收=`just schema-drift-check`

## 2. Runtime & workflow overrides

- [ ] 2.1 更新 output composition: effective `to.book` 仅来自 `outputs[*].to.book`,并更新缺失绑定的 fail-fast 文案/路径
- [ ] 2.2 移除 `RunOverrides.outputs_defaults` 与 runtime IO override 应用分支,并确保旧用法 fail-fast(不做兼容)
- [ ] 2.3 更新 workflow compile/entrypoints: 不再接受/透传 `overrides.outputs_defaults`,写入节点推导与 meta/audit 默认 book 选择仅依赖 `outputs[*].to.book`

## 3. CLI validation & diagnostics

- [ ] 3.1 更新 CLI demand/workflow validate: 移除对 `outputs_defaults.to.book` 的提取与诊断提示,统一提示 `outputs[*].to.book`
- [ ] 3.2 为“旧 YAML 仍包含 `outputs_defaults`”与“Excel output 缺失 `to.book`”补充可定位的错误信息与迁移提示(anchors/`$import` 复用)

## 4. Tests

- [ ] 4.1 更新/新增单测覆盖: `outputs_defaults` 字段与 overrides 被移除后的 fail-fast; Excel outputs 缺失 `to.book` 的错误路径稳定
- [ ] 4.2 更新 workflow 编译相关测试: 写入节点推导不再读取 `outputs_defaults`/`overrides.outputs_defaults`

## 5. Docs & generated artifacts

- [ ] 5.1 更新文档 SSOT: 移除 `docs/doc/yaml-dsl/*.md` 中对 `outputs_defaults` 的表述与示例,改为在 `outputs[*].to` 处显式 `book` 并用 anchors 复用
- [ ] 5.2 生成并校验 docs 生成物漂移: SSOT=`docs/doc/**/*.md` + schema json; 生成入口=`just gen-docs`; 验收=`just docs-drift-check`
- [ ] 5.3 生成并校验 skill references 漂移: SSOT=skill references 规则与 schema; 生成入口=`just gen-agent-skill`; 验收=`just validate-agent-skill`

## 6. Quality gates

- [ ] 6.1 运行 `just openspec-check` 确保 OpenSpec 工件一致性与可归档
- [ ] 6.2 运行 `just qa` 通过 lint/tests + drift checks

