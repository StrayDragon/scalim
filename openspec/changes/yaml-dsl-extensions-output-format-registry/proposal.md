## Why

当前输出创建逻辑高度内置(单输出与 composed outputs 仅支持少量内置格式),导致用户想快速试验新输出格式(如 parquet/jsonl/sqlite)时必须等待框架发版或改 driver 装配。

extensions 需要提供一个可审计、可回滚且可对拍的输出扩展入口: `format id → factory` registry,并让单输出与 composed outputs 共享同一套路由。

## What Changes

- 定义 `format_id → factory` registry API,可由 extensions/bundles 注入
- 单输出与 composed outputs 路由到同一 registry(保留内置输出;YAML `workbook/csv` 对应 execution `excel/csv`)
- YAML schema/models 支持:
  - `outputs[*].container.type` 使用自定义 format id
  - `outputs[*].container.options` 作为扩展配置(dict)透传给 factory
- 支持容器型输出(handle)以复用底层资源(workbook/sqlite/zip 等),并以确定性 `container_key` 缓存
- 回归测试: 自定义 format factory end-to-end(单输出 + composed outputs)

## Capabilities

### Modified Capabilities

- `output-composition`
- `yaml-dsl-schema`

## Impact

- 影响输出装配边界: `src/scalim/execution/run_ir.py`, `src/scalim/execution/output_composition.py`

## Dependencies

- 依赖 `yaml-dsl-extensions-host-core`: format registry 来源为 `ExtensionHost` 的编译产物
- 依赖 `yaml-dsl-extensions-schema`: schema/loader 需要先能承载 `extensions.outputs.formats` 与 `container.options`
