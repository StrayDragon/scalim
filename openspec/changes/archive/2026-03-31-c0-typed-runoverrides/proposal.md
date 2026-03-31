## Why

`RunOverrides` 当前以 YAML-shaped `dict/list[dict]` 作为对外契约,在下游“动态选字段/动态导出路径”的主流场景中非常常见,但带来两类长期问题:

- 下游容易把“当前 YAML 结构细节”固化成代码,当 schema/实现演进时出现高频破坏。
- 框架内部需要维护多处 dict 解析/校验逻辑(runtime/workflow 各一套),导致语义漂移、可维护性差、错误信息不稳定。

在外部已升级到 `scalim==0.5.1` 的前提下,我们可以用一次明确的 BREAKING 变更,把 overrides 的公共契约收敛为**强类型 dataclasses + 标准工厂方法**,从根上降低未来迭代的破坏面。

## What Changes

- **BREAKING**: `scalim.dsl.by_yaml.RunOverrides` 中以下字段不再接受 YAML-shaped `dict/list[dict]`:
  - `outputs`
  - `resources`
  - `outputs_defaults`
- **BREAKING**: 移除内部实现导入路径 `scalim.dsl.by_yaml.config_parsing.*`(旧路径将 `ModuleNotFoundError`),内部实现迁移到 `scalim.dsl.by_yaml._internal.config_parsing.*`。
- 新增一组**受约束的 overrides dataclasses**(以及必要的嵌套类型),用于表达 “detail 输出 + IO 覆盖” 的最小子集(与现有能力一致,但不再以 dict 表达)。
- `RunOverrides` 提供若干 `@classmethod` 工厂方法覆盖主流导出场景(例如单表单 sheet 动态字段导出),鼓励下游使用标准构造方式而不是手写结构。
- by_yaml runtime 与 workflow 编译链路不再解析 dict overrides,改为直接消费上述 dataclasses 并映射到内部 schema/IR。
- 文档/示例/测试用例统一升级为 dataclasses 写法(不保留旧写法兼容示例)。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `yaml-dsl-output-overrides`: overrides 输入结构从 YAML-shaped dict 变更为 typed dataclasses,并新增标准工厂方法与 fail-fast 迁移提示。

## Impact

- Public API:
  - `scalim.dsl.by_yaml.RunOverrides` 的字段类型与用法发生 BREAKING 变化
  - `scalim.dsl.by_yaml` facade 需要导出新增 overrides dataclasses(作为稳定入口)
- Runtime:
  - `src/scalim/dsl/by_yaml/runtime/contracts.py`(契约类型)
  - `src/scalim/dsl/by_yaml/runtime/compiler.py`(overrides 处理链路)
- Workflow:
  - `src/scalim/dsl/by_yaml/workflow_entrypoints.py`
  - `src/scalim/dsl/by_yaml/workflow_compile.py`
- Docs / Examples / Tests:
  - `docs/doc/yaml-dsl/user-guide.md` 等用户材料中的 overrides 示例
  - `tests/yaml_dsl/**` 与 `tests/workflow/**` 中的 overrides 覆盖用例
