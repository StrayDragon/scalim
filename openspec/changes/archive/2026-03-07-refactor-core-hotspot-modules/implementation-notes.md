## 热点盘点

### DSL runtime / validator
- `src/IMPL_ROOT/dsl/by_yaml/config_parsing/validators/fields.py`
  - 当前职责: 主/从源字段收集、derived 字段校验、output 字段校验、依赖解析、issue 汇总
  - 稳定入口: `IMPL_ROOT.dsl.by_yaml.config_parsing.validator`、`IMPL_ROOT.dsl.by_yaml.config_parsing.loader`
  - 拆分目标: source/derived/output 三类规则职责拆开,保留 `ValidatorFieldsMixin` 作为 facade
- `src/IMPL_ROOT/dsl/by_yaml/runtime/conversion.py`
  - 当前职责: lookup cast 注册、Config→IR 转换、relation 路径推导、binding 参数构造
  - 稳定入口: `IMPL_ROOT.dsl.by_yaml.runtime.conversion`、`IMPL_ROOT.dsl.by_yaml`
  - 拆分目标: lookup cast / source-field conversion / relation conversion / binding helpers 分拆,保留 `ConfigToIRConverter` facade

### hooks / observability / visualization
- `src/IMPL_ROOT/hooks/base.py`
  - 当前职责: hook 协议/基类、注册管理、typed/on_event 订阅缓存、typed 事件触发
  - 稳定入口: `IMPL_ROOT.hooks.base`
  - 拆分目标: protocol/base、registry、dispatch cache、typed trigger 分拆,保留 `HookManager` facade
- `src/IMPL_ROOT/ob/manager.py`
  - 当前职责: observer 注册、supports/wants 缓存、capture/replay 状态、typed 事件包装
  - 稳定入口: `IMPL_ROOT.ob.manager`
  - 拆分目标: registry/cache、capture state、emit helpers 分拆,保留 `ObserverManager` facade
- `src/IMPL_ROOT/ob/presets/viz.py`
  - 当前职责: config 路径解析、JSONL emitter、node ref 规范化、snapshot/trace 产物写入、事件映射
  - 稳定入口: `IMPL_ROOT.ob.presets.viz`
  - 拆分目标: config、emitter、runtime helpers、event handlers 分拆,保留 `VizObserverConfig` / `VizObserver` facade

### adaptive execution
- `src/IMPL_ROOT/execution/adaptive/loadref_scheduler.py`
  - 当前职责: worker 数解析、layer planning、task 提交、聚合提交、调度决策事件发射
  - 稳定入口: `IMPL_ROOT.execution.adaptive.loadref_scheduler`
  - 拆分目标: planning helpers、task runner、scheduler orchestration 分拆,并进一步对齐现有 `*_unit.py`

## 保护性测试映射
- 稳定导入/外部消费者样式: `tests/test_hotspot_refactor_guards.py`
- hooks pickle/cache: `tests/test_hook_manager_dispatch.py`
- observer wants/capture/fallback: `tests/test_hooks.py`
- viz 产物兼容: `tests/test_execution_run_ir.py`
- adaptive 调度/后端/顺序: `tests/test_execution_pipeline.py`
- YAML runtime/allowlist/转换器契约: `tests/test_yaml_runtime_contracts.py`
- hashseed 与参数顺序稳定性: `tests/test_deterministic_ordering.py`

## 实施顺序与 review 边界
1. 先补文档与守护测试,冻结稳定入口与受控外部消费者样式.
2. 先做 DSL runtime / validator,仅做内部职责迁移,不改公开导入路径.
3. 再做 hooks / observer / viz,保持 pickle/线程安全/输出契约不变.
4. 最后做 adaptive scheduler,优先复用 `strategy_unit.py` / `submission_unit.py` / `aggregation_unit.py`.
5. 每条主线独立跑定向测试;最终统一跑类型检查、Py3.6 检查、OpenSpec 校验.

## 受控外部消费者边界
- 本次实现默认存在至少一个受控外部消费者依赖 `YamlDemandLoader`、`load_output_config` 与 YAML DSL 顶层运行入口.
- 重构仅允许内部实现搬迁;若某处必须升级外部调用,应一步迁移到新写法,但不在 change 工件中记录真实项目路径.

## adaptive phase 完成记录
- `src/IMPL_ROOT/execution/adaptive/loadref_scheduler.py` 保持稳定 facade 与导出面,继续由 `AdaptiveLoadRefScheduler` 负责 orchestration.
- `src/IMPL_ROOT/execution/adaptive/_internal/loadref_scheduler_support.py` 负责 worker 数解析、分层 helper、process task runtime 构建与 `AdaptiveTaskResult`.
- `src/IMPL_ROOT/execution/adaptive/_internal/loadref_scheduler_planning.py` 负责 layer 可执行算子筛选、并行决策、task pool 解析、结果提交与决策事件发射.
- `src/IMPL_ROOT/execution/adaptive/_internal/loadref_scheduler_execution.py` 负责执行器工厂、capture runtime、pool 提交桥接等执行期职责.
- 与现有 `strategy_unit.py` / `submission_unit.py` / `aggregation_unit.py` 的边界已对齐: task 规格归一、pool 限流/提交、结果聚合提交分别保持在既有 unit 中,未重新聚回 facade.

## 外部消费者兼容检查(脱敏)
- 已检查一个受控外部消费者中的相关调用点,命中的是稳定 YAML facade: `IMPL_ROOT.dsl.by_yaml` 顶层 `run` / `RunOverrides` / `OutputOverrides`, `YamlDemandLoader`, 以及 `load_output_config`.
- 未发现其直接依赖本次新增 `_internal` 路径或新的 manager / viz / adaptive 私有实现.
- 因本次重构保持了上述稳定入口,该外部消费者当前不需要额外适配;后续若升级写法,也应继续走公开 facade,不暴露内部路径.

## 统一验证结果
- 相关热点回归测试: `245 passed`.
- `just type-check`: `0 errors, 0 warnings, 0 notes`.
- `just py36-compat-check`: 通过 (`python:3.6` compileall).
- `openspec validate --all --strict --no-interactive`: 通过.
