## Context

本变更聚焦于“可信单机场景默认可用,但在不可信输入/多租户/服务端并发导出时会放大风险”的若干 QA/安全问题,覆盖执行层输出(output_composition + sinks)、派生聚合(derived_outputs)、YAML params 模板(rows 绑定缓存)、工程质量门禁(just qa 的 py36 检查)以及 streaming 管线的回归护栏。

约束:
- 运行时需兼容 Python 3.6;避免 3.7+ 语法特性。
- 变更尽量低成本、可回滚,对“需要保留旧行为”的路径提供显式开关。
- 测试基线为 pytest + coverage 100%(核心模块)。

## Goals / Non-Goals

**Goals:**
- 默认情况下减少输出落盘信息泄露面(尤其是异常 message)并提供可控的“排障开关”。
- 为 Excel 输出提供可选的公式注入防护,并允许显式开启公式写入。
- 为高风险的“无限制聚合/rows 缓存”提供明确的 warn/文档与更保守的默认。
- 为并发写同一路径提供低成本的 fail-fast/lock 策略,避免静默覆盖。
- `just qa` 的 py36 兼容性门禁强制使用 docker,不再静默降级;并补齐回归护栏。
- 为 streaming rows 绑定屏障/行释放协调器补齐关键“行为不变”测试,支撑后续重构。

**Non-Goals:**
- 不尝试在库内部“完全解决多租户安全问题”(例如对所有文件写入做强制沙箱);多租户仍需外部运行隔离与路径约束。
- 不引入新的重量级依赖(如跨平台文件锁库)。
- 不做与本次清单无关的重构或性能优化。

## Decisions

### 1) meta/audit `error_message` 的默认落盘策略

**Decision:** meta/audit 默认不再写入原样 `str(exc)`;改为:
- `error_type` 保留
- `error_message` 改为安全摘要(例如空字符串/固定占位 + 稳定 hash + 可选短预览),并保证不会包含多行/超长内容
- 提供显式开关允许写入完整 message(仅可信环境排障)

**Rationale:** 异常 message 常携带 SQL/URL/token/PII,落盘即形成数据泄露面。默认写安全摘要仍可用于“同类错误聚合/对拍”,完整 message 仅在可信环境启用。

**Alternatives:**
- 仅截断(仍可能泄露敏感字段):拒绝。
- 永远不写 message(排障体验差):采用“安全摘要 + 开关”折中。

### 2) Excel 公式注入防护的实现位置与配置方式

**Decision:** 在 `sink_excel` 写入前对“疑似公式字符串”做转义,默认开启;同时提供显式允许模式以支持写入公式。

**Rationale:** 公式注入是输出侧典型风险,在 sink 层集中处理成本最低且覆盖面最大(ExcelSink/ExcelWorkbookSink/ColumnExcelSink)。

**Alternatives:**
- 仅文档提示:风险仍默认存在,不满足“高优先级 QA”目标。
- 在更上层做数据清洗:容易遗漏,且不利于复用。

### 3) 派生聚合 `max_groups=0` 的资源耗尽告警

**Decision:** 保持 `max_groups=0` 语义不变(不设上限),但在运行期输出明确 warn(一次性),提示用户设置上限以避免高基数 group-by 拖垮内存。

**Rationale:** 该行为属于“可信用户能力”,但默认无告警会让风险隐形。warn 成本低且不改变结果。

### 4) `$rows` 批次复用的内存驻留控制

**Decision:** 保持 `$rows.cache_mode` 语义不变(仍支持 `batch/none`),但当 `cache_mode=batch` 时默认不再在长生命周期缓存中保留完整 `batch_rows` 快照(避免大 batch 放大驻留);同时补齐明确文档/日志提示:
- `cache_mode=batch` 适用于“纯函数/无副作用”且希望复用 ref loader 结果的场景
- 若 loader 有副作用或依赖可变 `batch_rows`,应显式使用 `$rows: {cache_mode: none}` 禁用复用

**Rationale:** `batch_rows` 可能非常大,将其存入 cache 会显著放大内存驻留,且对复用结果本身并非必要(复用依赖的是结果映射).通过默认不缓存 `batch_rows` 可以显著降低内存风险,同时保持复用能力。

**Alternatives:**
- 改默认 cache_mode 为 none:会造成性能退化并引入更大的行为差异;暂不采用。
- 仅增加日志:仍默认驻留,无法实质降低风险。

### 5) 并发写同一路径的低成本处理

**Decision:** 提供低成本的 fail-fast/lock 策略,优先“默认不改变单机可覆盖行为”,但为服务端场景提供一行配置即可启用的保护(例如 lock 文件或 `if_exists=fail`).

**Rationale:** 静默覆盖对服务端并发导出是高风险脚枪;强一致 lock 成本可控,且不需要引入外部依赖。

### 6) `just qa` 的 py36 门禁必须依赖 docker

**Decision:** 移除无 docker 时的“静态兜底检查”,改为直接失败并提示安装/启动 docker;同时增加回归护栏(测试/脚本)防止未来被改回降级模式。

**Rationale:** 兜底检查覆盖不足,会造成“通过但不代表真实 py36 可跑”的错误安全感;门禁应 fail-fast。

### 7) streaming rows 屏障/行释放协调器的回归护栏

**Decision:** 增加针对 rows binding barrier + row release coordinator 的关键不变式测试(行为导向,避免依赖私有实现细节),确保未来重构不会破坏释放时机与屏障语义。

## Risks / Trade-offs

- [meta/audit message 变更] → 可能影响依赖 `error_message` 排障的用户 → 提供显式开关落完整 message,并在变更说明中强调。
- [Excel 默认转义] → 可能影响“用输出写公式”的用户 → 提供允许模式并在文档中给出迁移方式。
- [`$rows` 默认改为 none] → 性能可能下降(同一 relation 被多个字段复用时会重复调用) → 用户可显式设置 `cache_mode: batch` 恢复旧行为。
- [lock/fail-fast] → 可能引入“锁残留/失败”新运维点 → 错误信息包含清晰的恢复指引(清理锁/改用唯一路径)。
