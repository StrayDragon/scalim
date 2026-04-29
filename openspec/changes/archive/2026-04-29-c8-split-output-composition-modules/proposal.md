## Why

`src/scalim/execution/output_composition.py` 当前混合了:
- spec/数据类定义(`OutputCompositionSpec`、`OutputTargetSpec`、derived specs 等)
- 路由器实现(`RouterRowSink` 与内部状态机)
- 工厂/构建函数(`build_output_composition` 等)

这导致该文件成为 execution 层的“热点大杂烩”: 改一个小规则往往需要在巨大文件中穿梭,并且容易引入不相关回归。

在你希望的“更好的建议”框架下,我建议把此类热点按职责拆分,并让对外入口保持稳定: 这样后续无论是序列化治理(M-3)还是 derived outputs 扩展,都可以在更小的边界上推进。

## What Changes

- 将 output composition 按职责拆分为子模块/子包:
  - `output_composition/specs.py`: spec dataclasses + fingerprint helper
  - `output_composition/router.py`: `RouterRowSink` 与内部 routing state
  - `output_composition/build.py`: `build_output_composition` 与 plan builder
  - `output_composition/sinks.py`: csv/excel sink 创建辅助
- 保留原有稳定导入路径 `scalim.execution.output_composition`:
  - 文件可作为 facade,仅 re-export 对外类型/函数
  - 对外 API 行为不变

## Capabilities

### New Capabilities

- （无）

### Modified Capabilities

- `governance-module-organization`: 将 output composition 热点模块拆分为职责单一子模块,降低复杂度并提升可测试性。

## Impact

- 受影响代码:
  - `src/scalim/execution/output_composition.py`
  - 新增 `src/scalim/execution/output_composition/` 子包或 `_internal` 子模块
- 受影响测试:
  - 不应改变行为;现有 output composition 测试应全部通过
  - 拆分后可为 fingerprint/route rules 补充 unit tests
