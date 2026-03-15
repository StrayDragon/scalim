## Why

extensions 需要允许“宏/默认值注入/装配覆盖”等在编译期发生,并且必须在 validator 前生效,否则会出现校验与运行不一致(例如:校验看不见宏展开后的字段,或运行期看到与校验不同的结构)。

## What Changes

本 change 定义并落地 “transformers 的编译管线落点”(不引入新的业务语义):

- 定义 transformer stage APIs: `raw/config/ir/request`
- raw transformers 在 imports 展开后、核心 validator 前执行(保证宏展开/默认值注入对校验与编译一致可见)
- config/ir/request transformers 在 compiler pipeline 对应阶段执行
- 确定性顺序 + 错误上下文(`yaml_path/ref/stage`)
- 回归测试: raw transformer 影响校验与后续编译行为一致

示例(展示声明形态;具体 transformer 实现由用户提供):

```yaml
extensions:
  transform:
    raw:
      - ref: myapp.scalim_ext.transform:expand_macros
        config: {profile: dev}
```

## Capabilities

### Modified Capabilities

- `yaml-dsl-extensions`

## Impact

- 影响 YAML loader/compiler 的编排边界: `src/scalim/dsl/by_yaml/**`
- 不改变无 `extensions` YAML 的行为

## Dependencies

- 依赖 `yaml-dsl-extensions-host-core`: transformer 列表来自 `ExtensionHost` 的编译产物
- 依赖 `yaml-dsl-extensions-schema`: schema/loader 需要先能承载 `extensions.transform.*`
