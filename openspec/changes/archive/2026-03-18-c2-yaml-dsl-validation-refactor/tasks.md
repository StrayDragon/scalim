## 0. 基准与生成物边界

- [x] 0.1 记录基准行为与测试基线：`just test` 全绿；保留一份代表性 YAML fixture 用于后续对比 validate/schema-validate 输出
- [x] 0.2 若需修改 YAML DSL JSON Schema：SSOT 为 `src/scalim/dsl/by_yaml/schema_dsl/models/**/*.py`；生成入口 `just gen-yaml-dsl-schema`；验收口径 `tests/test_yaml_schema_generation.py` + `just test`（本次未改 schema SSOT；已通过 drift gate）
- [x] 0.3 若需修改 docs 的 `.gen.` 或 injected-block：SSOT 为对应非 `.gen.` 文档；生成入口 `just gen-docs`；验收口径 `just qa`(含 drift gate)（本次未改 docs SSOT；已通过 drift gate）

## 1. Schema issues collector 收敛

- [x] 1.1 抽取共享的 schema issues collector（统一 `Draft7Validator.iter_errors`、稳定排序、可选过滤 additionalProperties）
- [x] 1.2 `ConfigValidator._validate_with_jsonschema` 迁移到 shared collector（保持 best-effort：缺依赖/非预期异常 → warning，继续内部语义校验）
- [x] 1.3 `PROJECT_CLI_NAME yaml-dsl schema validate` 复用同一 collector（保持 schema-only：缺依赖 → error）
- [x] 1.4 保持 oneOf/anyOf 的 context 子错误仅在 `--verbose` 输出（默认输出不展示 context 噪音）

## 2. unknown-fields 覆盖 oneOf/anyOf + items

- [x] 2.1 扩展 `find_unknown_fields` 的 schema traversal：支持 `allOf/oneOf/anyOf` 的 best-match 分支选择 + 回退 union，并支持数组 `items` traversal（例如 `outputs.0`）
- [x] 2.2 增加 unit tests：覆盖 `oneOf/anyOf` + items 下 mapping key 的 unknown-fields 检测（至少覆盖 `outputs.0.container.unknown_field`）

## 3. outputs.container.path `$init_var` 语义校验收敛

- [x] 3.1 抽取并复用 `$init_var` 节点结构校验 helper（single-key mapping、`$init_var` 非空字符串、拒绝额外键），并在 parser/runtime/ConfigValidator 三处统一调用
- [x] 3.2 增加回归测试：在无 `jsonschema` 环境下，`yaml-dsl validate` 仍能对 `outputs[0].container.path: {$init_var: output_path, other: 1}` fail-fast 且定位到 `outputs.0.container.path`

## 4. 去重与输出一致性

- [x] 4.1 实现“unknown-fields 与 additionalProperties 不重复”的去重策略（unknown-fields 诊断优先，保留 suggestions）
- [x] 4.2 增加 CLI 输出回归测试：`yaml-dsl validate` 与 `yaml-dsl schema validate` 的 schema error 列表应完整且稳定排序（路径稳定、条目不重复）

## 5. 验收与收尾

- [x] 5.1 跑 `just test`
- [x] 5.2 跑 `just qa`
- [x] 5.3 跑 `just openspec-check`
- [x] 5.4 将 change delta specs 同步回主规范 `openspec/specs/yaml-dsl-cli-validation/spec.md`（归档前完成，避免规范漂移）
