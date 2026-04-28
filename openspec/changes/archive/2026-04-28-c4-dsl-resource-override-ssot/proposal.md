## Why

`YAML DSL` 目前存在两条并行的编译链路:
- 单 demand 编译: `src/scalim/dsl/yaml_dsl/runtime/compiler.py`
- workflow 编译: `src/scalim/dsl/yaml_dsl/workflow_compile.py`

这两条链路在 outputs/resources override 的解析与校验上存在明显的复制粘贴(例如 outputs_defaults/to/book 解析、output_extras 解析、book/file resource override 的 IO-only overlay 等)。同时,同类配置错误在不同链路下抛出的异常类型不一致(有的路径抛 `ValueError/TypeError`,有的抛 `ScalimWorkflowConfigError` 且带 `path=`),会导致:
- 维护成本高,修复/扩展容易漏改一条路径
- 错误信息与错误类型不稳定,下游难以统一处理
- review 时难以确定“真正的 SSOT 行为”

你已经明确倾向于做去重(避免遗漏与维护困难),因此本 change 的目标是: 先把 override 解析收敛为 SSOT,并把 DSL 层配置错误统一为 `ScalimWorkflowConfigError`。

## What Changes

- 提取共享的 override/patch 解析模块(SSOT):
  - `RunOverrides.outputs` / `outputs_defaults` / `resources` / `output_extras` 等解析与校验逻辑
  - demand 编译与 workflow 编译复用同一份实现
- 统一 DSL 层异常:
  - 将 runtime compiler 中散落的 `ValueError/TypeError` 统一包装/替换为 `ScalimWorkflowConfigError`(并保留 `path=`)
  - 保证 workflow 与 demand 看到的错误类型一致、路径可定位
- （不在本 change 内做的大拆分）对 `workflow_compile.py` 的模块化拆分可作为后续 change,但本 change 会先把最“重复/最易漂移”的 override 解析从大文件中抽走,降低后续拆分成本。

## Capabilities

### New Capabilities

- （无）

### Modified Capabilities

- `yaml-dsl-output-overrides`: override 的解析/校验必须通过同一条 SSOT pipeline,并对外提供一致的 `ScalimWorkflowConfigError(path=...)` 诊断语义。

## Impact

- 受影响代码:
  - `src/scalim/dsl/yaml_dsl/runtime/compiler.py`
  - `src/scalim/dsl/yaml_dsl/workflow_compile.py`
  - 新增 `src/scalim/dsl/yaml_dsl/_internal/<ssot_module>.py`
  - 相关测试(覆盖 invalid overrides 的错误类型与 path)
- 破坏性:
  - **BREAKING**: 下游若捕获 `ValueError/TypeError` 来判断 DSL 配置错误,需要迁移为捕获 `ScalimWorkflowConfigError`。
