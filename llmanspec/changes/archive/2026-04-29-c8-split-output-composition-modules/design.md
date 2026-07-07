## Context

### 调研: output_composition.py 的职责分布(关键路径)

从 top-level 定义可见,该模块大体包含:
- Spec/数据类层:
  - `OutputTargetSpec`、`DerivedGroupBySpec`、`OutputCompositionSpec` 等
  - fingerprint/hash helpers
- Runtime 实现层:
  - `RouterRowSink` (含大量状态与路由规则)
  - `OutputCompositionPlan` 与 route state
- Builder/工厂层:
  - `required_demand_fields(...)`
  - `build_output_composition(...)`
  - sink 创建函数

当前混合导致:
- 规则函数难以 unit-test(需要 import 巨大模块并带入许多运行期依赖)
- 任何改动都会触发大文件 review 与 merge 冲突

## Goals / Non-Goals

Goals:
- 将 spec 层与 runtime/router 实现解耦,并保持 stable API。
- 让最核心的 routing rules 与 fingerprint 逻辑具备更小的单测入口。

Non-Goals:
- 不改变 output composition 的对外行为或数据模型(纯重构)。
- 不在本 change 内处理 `predicate: Callable` 的可序列化问题(M-3)(若要处理可另开 change)。

## Decisions

1. 文件布局

推荐:
- 新建子包 `src/scalim/execution/output_composition/`:
  - `__init__.py` 仅 re-export 稳定符号
  - `specs.py`、`router.py`、`build.py`、`sinks.py`
- 原 `output_composition.py` 变为薄 facade 或直接 move 到子包内并保留兼容入口(以本仓库“不做兼容”的策略,更倾向于直接把旧文件变为 facade,对外 import path 不变)。

2. 依赖方向
- `specs.py` 不依赖 execution runtime 的重型模块(尽量只依赖 typing/dataclasses/util)。
- `router.py` 依赖 specs + sinks + runtime instrumentation。
- `build.py` 依赖 specs/router,负责组装 plan。

## Risks / Trade-offs

- [风险] 大规模移动符号可能导致循环依赖。
  - 缓解: 明确 specs -> router -> build 的单向依赖；必要时引入小型协议/回调接口以打断环。

- [风险] 纯重构引入回归。
  - 缓解: 每个搬运阶段跑 `just qa`,并保持对外导出符号一致。

## Migration Plan

- Phase 1: 抽出 `specs.py` (只移动 dataclasses 与 fingerprint helpers)
- Phase 2: 抽出 `sinks.py`
- Phase 3: 抽出 `router.py`
- Phase 4: 抽出 `build.py` 并让 facade re-export

## Open Questions

- 是否需要在 facade 上增加更明确的 `__all__` 白名单以防未来 symbol leakage?
> 需要