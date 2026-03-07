## Why

当前仓库已经明确识别出一组持续增长的核心热点模块:
- `src/IMPL_ROOT/dsl/by_yaml/config_parsing/validators/fields.py`
- `src/IMPL_ROOT/dsl/by_yaml/runtime/conversion.py`
- `src/IMPL_ROOT/hooks/base.py`
- `src/IMPL_ROOT/ob/manager.py`
- `src/IMPL_ROOT/ob/presets/viz.py`
- `src/IMPL_ROOT/execution/adaptive/loadref_scheduler.py`

这些热点模块的共同问题不是“功能错误”,而是“职责持续聚合”.若继续按现状演进,后续任何功能迭代都会抬高 review 成本、测试理解成本与局部替换成本.

团队已决定不再按多个独立 phase 分批提案,而是为这组热点模块准备一份一次性重构提案,作为统一 review 与实施基线.

## What Changes

- 发起一次覆盖上述全部热点模块的结构重构提案,并按统一 change 管理所有 phase.
- 将本次重构范围限定为“内部职责拆分 + 稳定入口保持 + 回归测试增强”,不把它扩展为新的产品功能变更.
- 对 DSL runtime / validator、hooks / observer / viz、adaptive scheduler 三条主线分别补充规范增量,确保实现阶段有明确边界.
- 要求重构后继续保持现有稳定导入入口、结果语义、事件语义与 Python 3.6 兼容约束.
- 本 change 作为宽口径重构提案基线;较窄的 manager-only 探索性 change 不作为最终实施范围依据.

## Capabilities

### New Capabilities

### Modified Capabilities
- `module-organization`: 明确本次一次性重构允许同时覆盖多个热点模块,并要求所有热点按职责拆分且保持稳定入口.
- `dsl-runtime-structure`: 明确 `validators/fields.py` 与 `runtime/conversion.py` 的职责拆分边界与稳定导出约束.
- `hooks-observability-structure`: 明确 `hooks/base.py`、`ob/manager.py` 与其管理器职责拆分要求.
- `execution-structure`: 明确 `adaptive/loadref_scheduler.py` 的调度链路拆分边界与稳定行为要求.
- `flow-visualization`: 明确 `ob/presets/viz.py` 的配置、事件映射、快照增强、文件输出职责拆分要求.

## Impact

- 主要影响 `src/IMPL_ROOT/` 内部组织与测试结构,不预期新增用户侧 API.
- 相关测试需覆盖稳定导入入口、线程安全、pickle roundtrip、事件顺序、viz 产物一致性与 adaptive 提交顺序.
- 需要保持 Python 3.6 兼容、`typing_extensionsx` 使用边界与现有公开导入路径不变.
