## Why

当前 QA/安全基线存在若干“低成本但高风险”的脚枪: 输出侧会把异常 message 落盘(meta/audit),Excel 输出对公式注入无防护,聚合输出对高基数 group-by 默认无限制,rows 绑定缓存可能放大内存驻留,并发写同一路径仍可能静默覆盖,以及 `just qa` 的 py36 兼容性门禁在无 docker 环境会降级为“静态兜底检查”(覆盖不足且容易给出错误安全感).

这些问题多数不影响单机可信场景,但会在多租户/不可信输入/服务端并发导出场景放大为安全或稳定性事故,需要优先收敛为明确可执行的规范与门禁,并补齐低成本的默认防护/告警.

## What Changes

- 输出 meta/audit 中的 `error_message` 默认不再原样落盘,改为“安全摘要”(例如 `error_type` + 稳定 hash + 可选短预览);提供显式开关允许落完整 message(仅用于可信环境排障).
- `OutputSpec.path` 继续允许任意路径写入(保持“可信配置”能力),但补齐明确的多租户使用规范: 必须外部约束/覆盖 `path`(例如限定输出根目录/禁用文件输出).
- Excel 输出新增“公式处理策略”:
  - 安全模式: 对疑似公式字符串做前缀转义(避免 `=HYPERLINK(...)` 等被当作公式执行)
  - 允许模式: 保持现有行为,允许写入公式(显式启用)
- 派生聚合输出: 当 `max_groups=0`(不设上限)时输出明确 warn(仍信任用户),并将该风险写入可复用文档/注释.
- rows 绑定缓存: 补齐“内存驻留放大”的告警与文档;默认避免在长生命周期缓存中保留完整 `batch_rows`(降低大 batch 的驻留放大).若加载器有副作用/依赖可变 `batch_rows`,继续通过 `$rows: {cache_mode: none}` 显式禁用复用.
- 并发写同一路径: 提供低成本的“防静默覆盖”策略(例如可选 lock 或 fail-fast),并将建议写入文档.
- `just qa` 的 py36 检查: 移除无 docker 时的兜底静态检查,强制使用 docker;无 docker 时给出明确失败信息与安装指引;增加回归护栏避免未来被改回降级模式.
- streaming 管线 rows 绑定屏障/行释放协调器相关逻辑补齐“行为不变”回归用例,为后续重构提供护栏.

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `output-composition`: meta/audit 的 error 记录策略与并发写出规范.
- `sinks-contracts`: Excel sink 的公式注入防护与并发写出策略.
- `derived-outputs`: 聚合输出 `max_groups` 风险告警与元信息 fingerprint 文档化.
- `source-relations`: `$rows.cache_mode` 的默认/推荐与内存驻留告警.
- `testing-quality`: `just qa` 的 py36 兼容性门禁必须依赖 docker,不得静默降级.

## Impact

- 受影响模块: `src/scalim/execution/output_composition.py`, `src/scalim/sinks/sink_excel.py`, `src/scalim/execution/derived_outputs.py`, `src/scalim/execution/executor/operators/load_ref/loader.py`, `src/scalim/dsl/by_yaml/params_template.py`, `src/scalim/dsl/by_yaml/schema_dsl/*`, `justfile`, `tests/**`.
- 可能的行为变化:
  - meta/audit 的错误信息字段默认更“克制”(排障依赖该字段的用户需要显式开启完整 message).
  - Excel 输出默认对“疑似公式字符串”做转义(如需输出公式需显式启用允许模式).
