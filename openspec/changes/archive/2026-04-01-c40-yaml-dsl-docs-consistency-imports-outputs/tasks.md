## 1. Review Gate (Maintainer)

- [x] 1.1 维护者确认该 change 为 docs/message-only,不引入行为变更
- [x] 1.2 维护者确认需要修正的漂移点清单(imports 语义、outputs.container 语义、过期迁移示例)

## 2. Docs SSOT Updates

- [x] 2.1 更新 `docs/doc/yaml-dsl/syntax.md`: imports/$import 的实际路径解析与限制边界
- [x] 2.2 更新 `docs/doc/yaml-dsl/capability-matrix.md`: outputs.container 仅 CSV; Excel 通过 books+to,并同步 imports 描述
- [x] 2.3 更新 `docs/doc/yaml-dsl/user-guide.md`: 移除/替换任何 workbook container 示例,给出当前有效写法

## 3. Diagnostics / Migration Messages

- [x] 3.1 更新 validator 迁移提示: 移除 workbook container 示例,替换为当前有效的最小迁移示例
- [x] 3.2 确保负例 fixtures 仅作为 rejection tests 存在,不被文档/提示引用为正例
- [x] 3.3 更新 skills 参考材料中错误示例(仅示例/迁移提示层面): `artifacts/skills/scalim-yaml-dsl/references/upgrades/2026-03-13-yaml-dsl-outputs.md`(移除 workbook container 示例,改为 books+to 写法)
- [x] 3.4 更新 skills 参考材料中错误示例(仅示例/迁移提示层面): `artifacts/skills/scalim-yaml-dsl/references/task-report-migration-playbook.md`(替换 legacy container 的 sheet 绑定字段为 `outputs.*.to.sheet` 与 `resources.books.*.write_lock`)

## 4. Generated Artifacts & Drift Gates

- [x] 4.1 生成并校验 docs 生成物漂移: SSOT=`docs/doc/**/*.md`; 生成入口=`just gen-docs`; 验收=`just docs-drift-check`
- [x] 4.2 若修改了 skills 参考材料,运行 skills 生成/校验入口以刷新 `*.gen.*` 并通过门禁(例如 `just gen-agent-skill` + `just validate-agent-skill` + `just generated-artifacts-drift-check`)

## 5. Quality Gates

- [x] 5.1 运行 `just openspec-check` 确保 OpenSpec 工件一致性
- [x] 5.2 运行 `just qa` 通过 lint/tests + drift checks
