## Context

当前 `HookManager` 与 `ObserverManager` 已经承担了多类职责:
- 订阅者注册/注销
- 事件类型过滤与 wants 语义
- handler 解析与缓存
- 高频事件分发
- capture / drain / replay 等状态管理
- pickling 后锁与内部状态恢复

这些职责集中在 `src/IMPL_ROOT/hooks/base.py` 与 `src/IMPL_ROOT/ob/manager.py` 两个热点文件内.从代码行为上看,现有实现已经可用且测试较强,因此本次 change 的目标不是改语义,而是在不打破稳定入口的前提下为后续拆分建立明确边界.

## Goals / Non-Goals

**Goals:**
- 将 `HookManager` / `ObserverManager` 的内部职责拆分为更清晰的子模块边界.
- 保持现有稳定入口继续可用,避免用户侧导入路径和装配方式震荡.
- 保持热路径分发语义、线程安全语义、pickling 恢复语义与当前实现一致.
- 为后续继续拆 `hooks/base.py` 与 `ob/manager.py` 提供可 review 的 phase 1 方案.

**Non-Goals:**
- 不修改 `components` 装配模型.
- 不引入新的 YAML DSL 配置或运行时开关.
- 不同时拆分 `runtime/conversion.py`、`loadref_scheduler.py` 等其它热点模块.
- 不改变 Hook / Observer 事件契约与 fallback 语义.

## Decisions

### Decision: 采用“外部稳定 facade + 内部职责子模块”方案
- 方案 A: 继续在单文件中通过 region/注释分段整理.
- 方案 B: 将管理器拆为 package,把注册管理/分发缓存/状态恢复放入内部子模块,包根或现有稳定模块继续暴露稳定入口.
- 结论: 选择方案 B.
- 理由: 单文件继续增长只会推迟问题;而完全改公共入口又会放大迁移成本.使用稳定 facade 可以兼顾可维护性与兼容性.

### Decision: Phase 1 仅拆 Manager 内部职责,不改调用方式
- 方案 A: 直接引入新的公开 manager API.
- 方案 B: 保持 `HookManager` / `ObserverManager` 类名与主要使用方式不变,只调整内部组织.
- 结论: 选择方案 B.
- 理由: 当前 change 的目标是结构治理,不是产品功能升级;应把风险压在内部实现层.

### Decision: 优先拆分的职责边界
- `hooks` 侧优先拆出: 订阅注册、handler 解析/缓存、dispatch 策略.
- `ob` 侧优先拆出: 订阅注册、wants / handler 缓存、capture/replay 状态、线程安全辅助.
- 共同约束: 锁恢复、pickle roundtrip 与 wants 热路径语义必须保持稳定.

### Decision: 保持现有测试语义,并增加结构回归测试
- 除保留既有功能测试外,新增针对“稳定导入路径、内部实现不泄漏、pickle/lock 恢复不退化”的回归测试.
- 结构重构必须由测试保护,而不是靠人工约定.

## Risks / Trade-offs

- [内部拆分后循环依赖变复杂] → 通过先定义最小职责接口、限制跨子模块回调方向缓解.
- [保持稳定入口导致短期同时维护 facade 与内部模块] → 接受该过渡成本,换取更低迁移风险.
- [重构触发隐藏的线程安全或 pickle 行为回归] → 在实施阶段优先补相关回归测试,以测试先行保护行为.
- [一次拆太多模块导致 review 面过大] → 本 change 限定为 hooks / observer managers phase 1,其它热点另开 change.

## Migration Plan

1. 先为 hooks / observer managers 增加结构与兼容性测试.
2. 再将内部职责迁移到子模块,保留既有稳定入口.
3. 在实现完成后运行相关单元测试、模块布局测试与 `openspec validate --all --strict --no-interactive`.
4. 若拆分中发现 scope 扩大,则停在 phase 1 边界,将额外问题留给后续独立 change.

## Open Questions

- `HookManager` 与 `ObserverManager` 是否都需要转为 package 形态,还是先保留文件入口并只抽内部 helper 模块?
- handler 缓存层是否值得在 hooks / observer 之间抽共享内部工具,还是先分别演进以降低耦合?
- `capture` / `replay` 状态是否应继续留在 `ObserverManager`,还是在 phase 2 中再单独拆离?
