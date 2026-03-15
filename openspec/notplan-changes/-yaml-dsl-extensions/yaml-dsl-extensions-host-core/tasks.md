**状态: TODO**

## 3. Extension Host Core (Registries + Bundles)

- [ ] 3.1 新增扩展宿主实现(建议独立子包,避免与 runtime/compiler 杂糅):
  - `src/scalim/dsl/by_yaml/runtime/extensions/__init__.py`
  - `src/scalim/dsl/by_yaml/runtime/extensions/contracts.py`:
    - `ExtensionBundle`(贡献集合)
    - `ExtensionHost`(最终合并视图;含 `summary`)
    - provenance/diagnostic 所需的最小数据结构(例如 source/ref/yaml_path)
    - 冲突策略枚举/类型(例如 `error|last_wins`)
  - `src/scalim/dsl/by_yaml/runtime/extensions/errors.py`: 统一错误包装,携带 `yaml_path/ref/stage`
  - `src/scalim/dsl/by_yaml/runtime/extensions/host.py`: `build_extension_host(...)`(解析 + 合并)
- [ ] 3.2 实现 `ref + config` 的通用“实例化/调用”策略(兼容函数/类/工厂;可选 ctx),并确保失败时能输出可行动错误(含 ref + stage)
- [ ] 3.3 解析 YAML `extensions` 块:
  - `enabled` 缺省视为 `true`;当 `false` 时跳过所有解析/导入/执行
  - `api` 缺省视为 `1`;未知值 fail-fast
- [ ] 3.4 解析 direct config 并编译为“隐式 bundle”(仅构建扩展视图,不要求本 change 让其在 compute/output 语义上生效):
  - `extensions.compute.functions`(name → callable ref)
  - `extensions.outputs.formats`(format_id → factory ref/{ref, config})
  - `extensions.aggregates.kinds`(kind_id → factory ref/{ref, config})
  - `extensions.transform.{raw|config|ir|request}`(stage → [{ref, config}])
  - `extensions.analyze`(analyzers: [{ref, config}])
  - `extensions.components`([ref|{ref, config}])
- [ ] 3.5 解析并调用 `extensions.bundles`:
  - 逐项 resolve ref → call/instantiate(传入 config/ctx) → MUST 返回 `ExtensionBundle`
  - 相对引用必须复用 `SecurePythonReferenceResolver` 的 `base_module_path` 语义: 无 `yaml_path` 时 fail-fast
- [ ] 3.6 合并贡献(确定性):
  - 顺序: direct config(隐式 bundle) → bundles(按 YAML 顺序)
  - 冲突策略由 `extensions.conflicts` 控制,默认 `error`
  - 冲突错误必须包含冲突键名 + 来源列表(至少含 ref)
- [ ] 3.7 实现 `ExtensionHost.summary`(稳定结构,便于 CLI/CI/IDE 对拍),至少包含:
  - bundles 列表(含 ref)
  - registries 的 keys(例如 compute function names / format_ids / aggregate kind_ids)
  - transformers/analyzers/components 列表(含 ref)
- [ ] 3.8(最小集成)在 `src/scalim/dsl/by_yaml/runtime/compiler.py` 的编译链路中构造 `ExtensionHost` 并对外暴露(例如放入 `Compilation`),为后续 changes wire-up 做准备

## 6. YAML Components Injection

- [ ] 6.1 解析 `extensions.components` 并在编译期 resolve/instantiate(复用 3.2 的通用调用策略)
- [ ] 6.2 在 `src/scalim/dsl/by_yaml/runtime/compiler.py::build_request(...)` 将 extensions components 与现有 components 合并:
  - 顺序建议: driver components → extensions.components → observability observers
- [ ] 6.3 在装配阶段复用 `src/scalim/ob/components.py::split_components(...)` 做 fail-fast 类型校验
- [ ] 6.4 新增回归测试(建议新增独立 fixture module 供 allowlist 引用):
  - `tests/fixtures/extensions_mod.py` 提供可引用的 Observer/Hook 工厂
  - `tests/test_yaml_dsl_extensions_components.py`:
    - 合法 Observer/Hook 可被装配并出现在 `ExecutionRequest.components`
    - 非法对象 fail-fast 且报错包含 index/type

## Gates

- [ ] `just qa`
- [ ] `just openspec-check`
