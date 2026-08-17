# Observer / Hook 二开扩展（继承 + 组合）

面向 Agent：下游要**定制观测或执行钩子**时读本卡。装配 profiles / run_stats 读 `scalim-run-stats`；本卡只讲扩展面。

## 何时用

- 需要业务侧额外日志、指标、告警、旁路落盘
- 需要在执行路径上做策略钩子（Hook），而不只是旁路观察（Observer）
- **不要**为日常对拍再抄一份 PerformanceObserver / StatsBundle

## 稳定扩展点（优先）

| 方式 | 基类 | 用途 |
|------|------|------|
| 组合 | `components=[builtin..., MyObs()]` | **推荐**：内置 presets + 自研旁路 |
| 继承 Observer | `EventDispatchObserver` 或 `Observer` | 只读观测；typed `on_*` 或统一 `on_event` |
| 继承 Hook | `BaseHook`（`from scalim.hooks import BaseHook`） | 可参与执行策略的钩子 |

进程内身份：`EventType` only。typed handler 入参是完整 **`Event`**（`event.payload` / `event.meta`），见 `upgrades/2026-08-02-typed-handlers-receive-event.md`。

## 最小 Observer 示例

```python
from scalim.events import Event, EventType
from scalim.ob.observer import EventDispatchObserver
from scalim.ob.presets.profiles import ObservabilityProfile, build_observability_profile

class LoaderAlertObserver(EventDispatchObserver):
    event_types = {EventType.LOADER_CALL}

    def __init__(self, warn_s=5.0):
        self._warn_s = float(warn_s)

    def on_loader_call(self, event: Event) -> None:
        p = event.payload
        if float(getattr(p, "duration", 0) or 0) >= self._warn_s:
            # 业务日志 / metrics；勿在热路径做重 I/O
            pass

built = build_observability_profile(ObservabilityProfile.BENCH, include_memory=False)
components = list(built["components"]) + [LoaderAlertObserver(warn_s=3.0)]
# DemandRunRuntimeOptions(components=components)
```

只实现 `on_event` 亦可：

```python
from scalim.ob.observer import Observer

class CatchAll(Observer):
    event_types = None  # 全部

    def on_event(self, event: Event) -> None:
        _ = event.event_type
```

## 最小 Hook 示例

```python
from scalim.hooks import BaseHook
from scalim.events import Event

class AuditHook(BaseHook):
    def on_pipeline_end(self, event: Event) -> None:
        _ = event.payload
```

Hook 与 Observer 都进同一 `components` 列表；不要从 YAML `observability.*` 配置（已移除）。

## 组合规则

1. **生产非 DEBUG**：`components=[]`；定制组件也不要默认挂上（见 `scalim-run-stats/.../task-downstream-env-gating.md`）。
2. **优先组合内置 profile**，再 `+ [MyObs()]`；避免 subclass 内部改 `PerformanceObserver` 私有状态。
3. **workflow**：共享同一 `components` 实例才能让 `WorkflowStatsAccumulator.nodes[]` 跨 demand；per-demand 额外组件用 `WorkflowNodePatch` / `ComponentsExtend`。
4. **高影响订阅**（`FIELD_COMPUTE` / `RELATION_LOOKUP` / viz trace|full）会抬观测税并可能触发 `UserWarning`；Agent 须明示税与 bench 替代。
5. keys 分片自证订阅 `LOADER_CALL`（`chunk_offset` / `lookup_key_count`）；并行完成序 + 可能在 worker 线程。见 `scalim-yaml-dsl/references/lookup-chunking-guidance.md` 与 `ch164_public_api_lookup_chunking`。
6. 可选 `close()` 做 flush；旁路 JSON 优先 `write_run_stats_sibling`，不要塞进 `viz_snapshot.json`。

## 不推荐

- 复制上游 preset 源码到业务仓库长期分叉
- 用 `TYPE_CHECKING` 伪造 Observer 接口
- typed handler 里写 `event.batch_size`（应为 `event.payload.batch_size`）
- 生产路径为「方便调试」常开 DEBUG profile

## 交叉

- 环境门控（生产静默 / 开发服 psutil）：`scalim-run-stats/references/task-downstream-env-gating.md`
- EventType / typed Event 升级：`task-event-type-adaptation.md`、`upgrades/2026-08-02-typed-handlers-receive-event.md`
- 人类完整说明（Why / ROI / 门控摘要）：`docs/doc/viz/run-stats.md`
- 人类 YAML 装配说明：`docs/doc/yaml-dsl/user-guide.md`（components 示例）
