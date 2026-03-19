## Context

本变更关注“框架内部日志”(非业务数据输出): 下游在执行过程中会看到来自多个子模块的 warning/info,但历史实现存在以下问题:

- 输出风格不一致: 不同模块混用不同前缀/标签(甚至类似 `[XxxObserver] ...` 的类名前缀),文案中中英文混杂,难以统一检索与排障。
- 缺少统一的结构化字段约定: 同类诊断信息在不同位置以不同形式输出,下游难以稳定解析(例如基于日志做告警/监控聚合)。
- 可选依赖异常噪音: 当 `jsonschema` 等可选依赖缺失或版本不兼容时,提示不够一致且可能重复出现,影响可读性。

约束:

- 必须使用 Python 标准库 `logging`(避免引入第三方 logging 框架依赖).
- 作为库代码必须默认静默: 不调用 `logging.basicConfig`,不主动安装 `handler/formatter`.
- 模块应可在框架内任意位置安全导入,避免循环导入与可选依赖牵连。
- “统一时间显示”仅在用户自行配置 `handler/formatter` 时生效;库端不保证输出时间字段。

说明: 本 change 为“反推归档”。实现与测试已在工作区完成,此设计用于固化关键决策与后续约束。

## Goals / Non-Goals

**Goals:**
- 在 `scalim` 框架内部形成统一的日志命名空间、前缀与字段追加约定,让日志在最小配置下仍可读、可 grep、可聚合。
- 提供一个只依赖标准库、可安全导入的日志工具模块,并在导入时完成库侧“默认静默”初始化。
- 提供可扩展机制: 允许实现侧绑定上下文字段(例如 `custom_server_id`、`target_id`),也允许用户侧通过 `formatter` 自定义时间/级别/输出结构。

**Non-Goals:**
- 不在库端安装任何 `handler`/`formatter`,也不改变 `root logger` 的配置。
- 不保证“统一时间显示”;时间字段由下游 `formatter` 决定。
- 不引入 `structlog`/`loguru` 等第三方 logging 框架,也不提供 JSON 日志渲染器/采集管道。
- 不改变执行/校验/护栏的业务语义;本变更仅规范输出形态与文案一致性。

## Decisions

1. **模块落点: `src/scalim/_internal/loggingx.py`**
   - 作为跨模块基础设施,放在 `IMPL_ROOT/_internal/` 下,并确保该模块仅依赖标准库(避免被任意子系统反向依赖导致循环导入).
   - 导入即完成一次性初始化: 对 `logging.getLogger(\"scalim\")` 安装 `logging.NullHandler()`。

2. **默认静默策略: `NullHandler` + 不做全局配置**
   - 在 `loggingx` 导入时为 `scalim` root logger 安装 `NullHandler`,避免库侧在无配置环境里产生 “No handler...” 警告。
   - 明确禁止在库端调用 `logging.basicConfig(...)` 或默认安装 `StreamHandler`/`Formatter`。

3. **logger 命名空间: `scalim` / `scalim.<subsystem>`**
   - 统一使用 `logging.getLogger(\"scalim\")` 作为 root。
   - 每个子系统通过 `get_logger(\"schema\")`、`get_logger(\"derived_outputs\")` 等方式获得子 logger,方便下游按模块过滤级别/输出目的地。

4. **前缀写入 message,不依赖 formatter**
   - 为了让“最小配置”也能读,统一把 `[scalim] <subsystem>:` 前缀直接写入 message(通过 `prefix(subsystem)`),不依赖用户侧 `formatter` 才能看到关键信息。
   - 代价: 若下游 `formatter` 同时打印 `%(name)s` 或自定义前缀,可能出现信息重复;但该冗余是可控且更符合库侧“尽量不替用户做决定”的原则。

5. **稳定 `k=v` 追加字段约定**
   - 使用 `format_kv(...)` 将诊断字段以 `k=v, k2=v2` 方式追加到 message 末尾:
     - key 按字典序排序,保证输出稳定.
     - `None` 值忽略,避免噪音字段.
     - 对 list/tuple/set/dict 做可读字符串化,其中 dict 优先 `json.dumps(..., sort_keys=True, ensure_ascii=False)`。
   - 不强制使用 `logging` 的 `extra` 字段作为默认承载(避免与下游 formatter 的字段冲突);但提供 `bind(logger, **ctx)` 作为可选扩展入口(基于 `logging.LoggerAdapter`).

6. **下游统一时间显示的推荐做法(库端不保证)**
   - 下游可以按标准库 `logging` 习惯自行配置:
     - 仅配置 `scalim` logger: `logging.getLogger(\"scalim\").addHandler(...)`
     - 或配置 root 并通过 logger 名称过滤
   - 时间显示由下游 `Formatter` 的 `%(asctime)s` 决定;库端不会输出时间字段。

## Risks / Trade-offs

- [日志字符串格式变更 → 下游解析回归] 若下游基于旧文案做规则匹配,需要迁移。缓解: 提供稳定前缀与稳定 `k=v` 追加字段,并在提案中标记 BREAKING.
- [前缀写入 message 可能与 formatter 重复] 下游若同时输出 `%(name)s` 或自定义前缀会出现重复信息。缓解: 这是可选配置问题,不在库端强制限制;下游可调整 formatter.
- [默认静默可能让“期待默认打印”的用户困惑] 但这是 Python 库使用 `logging` 的标准实践。缓解: 通过文档/提案强调“需要下游配置 handler 才会看到日志”。

## Migration Plan

- 代码侧无迁移步骤(仅输出形态变更).
- 下游如需继续采集/告警:
  - 更新日志解析规则为新前缀 `[scalim] <subsystem>:` 与 `k=v` 格式;
  - 若需要统一时间显示,在下游 `handler/formatter` 中增加 `%(asctime)s`。

## Open Questions

- (none)
