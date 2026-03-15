**状态: TODO**

## 2. Schema & Loader Scaffolding (pipeline)

- [ ] 2.3.1 重构 `src/scalim/dsl/by_yaml/config_parsing/loader.py` 为可编排步骤(保持现有 `load/load_string` 行为不变):
  - 提取“YAML parse + imports 展开”步骤为可复用函数/方法(例如 `load_raw(...)`/`load_raw_string(...)`)
  - 提取“parse RawDemand → DemandConfig”步骤为可复用函数/方法(例如 `parse_raw(...)`)
  - 使 runtime/compiler 能实现管线: `imports 展开 → build ExtensionHost → raw transformers → core validator → parse`

## 9. Transformers (raw/config/ir/request)

- [ ] 9.1 定义 transformer stage APIs + ordering(SSOT 来自 `ExtensionHost`):
  - stage: `raw/config/ir/request`
  - 单 stage 内确定性顺序: direct config → bundles(按 YAML 顺序)
  - 约定输入/输出类型与返回值语义(见 design.md)
- [ ] 9.2 raw transformers 落点:
  - 在 `imports` 展开后构建 `ExtensionHost`
  - 在 `ConfigValidator.validate(...)` 之前执行 raw transformers
  - validator 必须看到 raw transformer 之后的 raw dict
- [ ] 9.3 config/ir/request transformers 落点(建议集中在 runtime/compiler 的单一管线,避免多处重复):
  - `DemandConfig` 解析后执行 config transformers
  - `DemandIr` 构造后执行 ir transformers
  - `ExecutionRequest` 装配后执行 request transformers
- [ ] 9.4 诊断与错误包装:
  - 任意 transformer 异常必须包装 `yaml_path/ref/stage`
  - 错误信息必须可用于定位到具体 transformer(含 ref)
- [ ] 9.5 回归测试(建议新增独立 fixture module 供 allowlist 引用):
  - `tests/fixtures/extensions_transform_mod.py` 提供:
    - raw transformer: 把字符串类型的 `batch_size: \"2\"` 改写为整数 `2`(或注入缺省键)
    - config/ir/request transformer: 可观测的轻量变更(例如标记 meta 字段或调整 request 参数)
  - `tests/test_yaml_dsl_extensions_transformers.py` 覆盖:
    - raw transformer 运行在 validator 前: 未变换前会触发 schema/type 校验失败,变换后通过
    - stage 顺序与确定性: 多个 transformers 按声明顺序生效
    - 异常时错误包含 `yaml_path/ref/stage`

## Gates

- [ ] `just qa`
- [ ] `just openspec-check`
