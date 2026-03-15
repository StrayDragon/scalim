**状态: TODO**

## 5. Compute Functions Extension

- [ ] 5.1 扩展 compute engine 构造入口以注入扩展函数(name → callable):
  - `src/scalim/dsl/by_yaml/config_parsing/security.py::build_compute_engine(...)` 支持传入扩展函数映射并构造 `SecureComputeEngine(allowed_function_map=...)`
  - 确认扩展函数名进入 `allowed_functions`(可用于表达式 `safe_div(a,b)` 的 Call)
- [ ] 5.2 修复 compute 依赖推导(字段依赖推导必须忽略函数名):
  - 更新 `src/scalim/dsl/by_yaml/config_parsing/security.py::extract_dependencies_from_compute(...)`(或等价实现)以忽略 `ast.Call.func` 中的函数名
  - 增加单测覆盖: `safe_div(a, b)` 的依赖 MUST 仅包含 `a/b`
- [ ] 5.3 统一 compute engine SSOT(避免 validate/compile/run 漂移):
  - 在 extensions-aware 编译管线中,从 `ExtensionHost.compute_functions` 构造一次 compute engine(或构造等价实例),并向下游传递
  - 至少覆盖以下调用点使用同一套 engine:
    - `ConfigValidator`(语义校验)
    - YAML `outputs` parser 的 where 校验: `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py`
    - `compile_ir` / `ConfigToIRConverter`: `src/scalim/dsl/by_yaml/runtime/compiler.py`
    - runtime output composition 的 where predicate: `src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`
  - 确保无 `extensions` 或无 `compute_functions` 时行为不变(继续使用内置 SAFE_BUILTINS)
- [ ] 5.4 回归测试(端到端):
  - `tests/fixtures/extensions_compute_mod.py` 提供可 allowlist 引用的 `safe_div`
  - `tests/test_yaml_dsl_extensions_compute.py` 覆盖:
    - 派生字段 `fields.*.compute` 可使用 `safe_div`
    - `outputs[*].where` 可使用 `safe_div`
    - `safe_div` 不会被误判为未知字段依赖(依赖推导正确)

## Gates

- [ ] `just qa`
- [ ] `just openspec-check`
