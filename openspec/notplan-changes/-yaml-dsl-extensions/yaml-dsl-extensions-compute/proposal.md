## Why

extensions 的 compute/where 扩展属于“高频、小粒度”的真实需求:用户常常只想在 `compute`/`where` 里加一两个安全函数,不应被迫等待框架发版。

同时,compute 函数扩展必须在 **依赖推导/语义校验/IR 构造/运行期求值** 的全链路保持一致,否则会出现“validate 通过但运行失败(或反之)”的漂移。

## What Changes

- compute engine creation 支持注入扩展函数(name → callable)
- 修复 compute 依赖推导: 忽略函数名(`Call.func`),只收集字段名依赖
- validator + YAML outputs parser + runtime output composition 共享同一套扩展后的 compute engine
- 回归测试: 扩展函数在 derived `compute` 与 outputs `where` 中可用,且不会被误判为“未知字段”

## Capabilities

### Modified Capabilities

- `yaml-dsl-extensions`

## Impact

- 影响 compute/where 的编译链路: `src/scalim/dsl/by_yaml/config_parsing/security.py` 等

## Dependencies

- 依赖 `yaml-dsl-extensions-host-core`: 扩展函数来源为 `ExtensionHost.compute_functions`
- 依赖 `yaml-dsl-extensions-transformers`: 为了让 validator 在 extensions-aware 管线里拿到同一套 compute engine,需要先完成“build host → (raw transformers) → validate → parse”的管线重构
