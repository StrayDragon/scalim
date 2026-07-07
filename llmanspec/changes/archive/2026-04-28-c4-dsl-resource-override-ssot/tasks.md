## 1. SSOT Extraction

- [x] 1.1 在 `src/scalim/dsl/yaml_dsl/_internal/` 新增 `resource_override.py`(或等价命名)并迁移最明显重复的 helpers:
  - `outputs_defaults.to.book` 解析
  - `output_extras` 解析/overlay
  - default book binding 应用
- [x] 1.2 迁移 `RunOverrides.outputs` 的解析/校验为 SSOT 函数,并在 demand/workflow 两条路径复用
- [x] 1.3 迁移 `RunOverrides.resources` 的 books/files IO-only overlay 为 SSOT 函数,并在两条路径复用

## 2. Error Unification (BREAKING)

- [x] 2.1 将 runtime compiler 中 overrides/resources 相关的 `ValueError/TypeError` 全部替换/包装为 `ScalimWorkflowConfigError(path=...)`
- [x] 2.2 确保内部包装使用 `raise ... from exc` 保留异常链(除非明确属于 API 边界需要抑制)

## 3. Tests

- [x] 3.1 更新现有 YAML DSL overrides 测试,改为断言 `ScalimWorkflowConfigError` 类型与 `.path`
- [x] 3.2 新增回归测试: 同一非法 overrides 在 demand compile 与 workflow compile 两条入口下产生一致的错误类型与 path

## 4. Verification

- [x] 4.1 运行 `just qa`
- [x] 4.2 运行 `just openspec-check`
