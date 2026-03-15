**状态: TODO**

## 7. Output Format Registry (single output + composed outputs)

- [ ] 7.1 定义 `format_id → factory` registry API(SSOT),并能从 `ExtensionHost` 构造:
  - 新增模块: `src/scalim/execution/output_format_registry.py`(或等价位置),定义:
    - `OutputFormatRegistry`(lookup + create)
    - factory 的最小调用约定(接收 `path/layout/options` 等,见 design.md)
    - 容器型输出(handle)的最小协议(可选;用于资源复用)
  - 在 extensions-aware 编译管线中,从 `ExtensionHost.output_format_factories` + built-ins 构造 registry
- [ ] 7.2 单输出模式接入 registry:
  - 修改 `src/scalim/execution/run_ir.py::_create_file_sink(...)`:
    - 对内置 `csv/excel` 保持兼容
    - 当 `output.format` 为非内置值时,通过 registry 创建 sink(失败时给出可行动错误,包含 format_id)
- [ ] 7.3 composed outputs 接入 registry:
  - 修改 `src/scalim/execution/output_composition.py` 的 sink 创建逻辑:
    - 对内置 `csv/excel` 保持兼容且行为不变
    - 当 `output.format` 为非内置值时,通过 registry 创建 sink
    - composed outputs 对 sink 的约束保持为 `IRowSink`(非 row sink fail-fast)
- [ ] 7.4 YAML authoring surface 接入:
  - `src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py`:
    - `OutputContainerConfig.type` 放开为任意 string format id(不再固定 choices)
    - 新增 `OutputContainerConfig.options: Optional[dict]`(自由 dict)
  - `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py`:
    - 当 `container.type` 为非内置值时,允许其通过(具体是否存在于 registry 由 extensions-aware 校验决定)
  - `src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`:
    - 按 design.md 的 mapping 生成 `OutputSpec.format`(workbook→excel, csv→csv, 其它透传)
    - 透传 `container.options` 到 registry(factory),并确保 options 缺省为 `{}` 或 `None`
- [ ] 7.4.1 `container.options` runtime contract:
  - registry factory MUST 能接收 options(可为 `None`/空 dict)
  - 内置 `csv/excel` 忽略 `container.options`(不改变现有行为)
- [ ] 7.4.2 容器型输出(handle)支持(资源复用):
  - 将现有 excel workbook 复用逻辑抽象为“handle 缓存”(至少 composed outputs 支持)
  - `container_key` MUST 为确定性键(至少包含 format_id + path + options 的稳定表示)
  - 生命周期结束时 MUST close(复用现有 workbook close 路径)
- [ ] 7.5 回归测试(端到端):
  - `tests/fixtures/extensions_output_formats_mod.py` 提供可 allowlist 引用的自定义 format factory:
    - composed outputs: 返回 `IRowSink`
    - single output: 返回 `ISink`(可为 `IRowSink`/`IColumnSink`)
  - `tests/test_yaml_dsl_extensions_output_formats.py` 覆盖:
    - YAML `outputs[*].container.type: <custom>` 通过编译并路由到 factory
    - composed outputs 对非 `IRowSink` 的自定义 factory fail-fast
    - `container.options` 可被 factory 读取
    - 单输出模式 `output.format: <custom>` 通过 registry 生效

## Gates

- [ ] `just qa`
- [ ] `just openspec-check`
