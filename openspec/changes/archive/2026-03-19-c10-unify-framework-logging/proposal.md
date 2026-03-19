## Why

下游用户反馈框架内部日志“像是 `scalim` 自己打的”,但格式不美观且不一致: 不同模块混用不同前缀/中英文文案/非结构化字段,并且在可选依赖不兼容时会产生重复噪音输出(例如 `jsonschema` 导入失败后多次提示),导致排障成本升高,监控/告警也难以稳定解析。

同时,部分护栏/性能类日志(高基数 group-by、`count_distinct`、内存增长阈值等)属于运行期关键诊断信息,应当遵循统一的输出约定: 默认静默(库端不主动配置 `logging`),但一旦下游启用 `handler`/`formatter`,就能获得一致、可检索、可扩展的日志结构。

说明: 本变更为“反推归档”。实现与测试已在工作区完成,OpenSpec 用于固化行为边界与后续维护约定。

## What Changes

- 新增内部日志工具模块 `src/scalim/_internal/loggingx.py`:
  - 仅依赖标准库 `logging`,可在框架内任意位置安全导入(避免循环导入).
  - 对 `logging.getLogger(\"scalim\")` 安装 `NullHandler`,避免 "No handler could be found..." 等库侧噪音.
  - 不调用 `basicConfig`,不安装 `handler`/`formatter`,不强制时间格式。
- 统一框架内用户可见日志输出风格(**BREAKING: 日志文案/前缀变更**):
  - 统一前缀: `[scalim] <subsystem>: ...`(subsystem 如 `schema`/`derived_outputs`/`performance` 等).
  - 统一 `k=v` 追加字段格式(稳定排序、忽略 `None`),便于 grep/采集与下游扩展.
  - 统一通过标准库 `logging` 输出(按 `warning/info/debug`),不再混用自定义打印/非标准标签.
- 对几个关键热点的日志进行对齐与去噪(不改变执行语义,仅改输出):
  - YAML DSL schema 校验: `jsonschema` 不可用/依赖不兼容时,输出可定位 warning,并带 `reason/detail`.
  - 派生输出护栏: `max_groups=0`、`max_distinct=0` 等高基数风险提示带 `target_id/group_keys`.
  - 性能观测: 内存增长超过阈值的提示字段结构化(以 MB 输出关键字段).

## Capabilities

### New Capabilities
- `framework-logging`: 定义框架内部日志的命名空间、默认静默策略、前缀与 `k=v` 约定,并提供可扩展机制(如 context 绑定).

### Modified Capabilities
- (none)

## Impact

- 受影响代码(SSOT):
  - 新增: `src/scalim/_internal/loggingx.py`(统一入口)与 `src/scalim/_internal/__init__.py`
  - 改动: YAML 解析校验、派生输出、hooks/ob/sinks 等多处日志输出点(详见 `git diff --stat`)
- 受影响测试:
  - 新增: `tests/test_loggingx.py`
  - 更新: 若干回归测试中对日志文案/前缀的断言
- 对下游的影响:
  - 默认仍为“无 handler=无输出”(库端不保证时间显示);下游若配置 `handler/formatter`,可通过 `%(asctime)s` 等实现统一时间显示。
  - 若下游存在基于旧日志字符串的解析/告警规则,需要按新格式迁移(仅日志格式变更,数据与执行行为不变).
