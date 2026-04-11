## Meta

- Type: `qa-0`
- Topic: `yaml_dsl compute` 审计回调的日志脱敏/防泄密
- Related code:
  - `src/scalim/dsl/yaml_dsl/_internal/config_parsing/security.py:143` (`default_audit_callback`)
  - `src/scalim/dsl/yaml_dsl/_internal/config_parsing/security.py:149` (`redacted_audit_callback`)
  - `src/scalim/dsl/yaml_dsl/_internal/config_parsing/security.py:448` (`SecureComputeEngine.__init__(..., audit_callback=...)`)

## 背景

`yaml_dsl` 支持 `compute` 表达式（通过 `SecureComputeEngine` 做 AST 白名单校验后再 `eval`），并提供了可选的“求值审计”回调接口（`audit_callback(expression, field_values, result)`），用于调试与可观测性。

当前仓库提供了两个内置回调：

- `default_audit_callback(...)`：记录原始 `field_values` 与 `result` 到 debug log（注释中已经提示可能包含 `PII`）。
- `redacted_audit_callback(...)`：仅记录表达式 hash、字段名列表与结果类型（脱敏）。

问题在于：**一旦业务侧/集成侧启用 `default_audit_callback`，它会把数据行的原始字段值与计算结果写入日志**，在真实数据集上非常容易引发敏感信息泄露（日志系统往往比数据源更“广泛可见”、更难删除、更可能被采集/转存）。

## 现状与风险点

### 现状

- `SecureComputeEngine` 默认 `audit_callback=None`（未启用审计时无额外开销）。
- 但仓库对外暴露了 `default_audit_callback`，并且从命名上看很容易被当成“推荐默认值”直接使用。

### 风险示例（日志泄密）

假设某字段配置：

- `compute: "phone[-4:]"` 或 `compute: "id_card"`（仅示例）
- `field_values` 包含 `phone="13812345678"` 或身份证号、邮箱等

如果启用了 `default_audit_callback`，debug 日志会出现类似：

- `表达式='phone[-4:]' 字段={'phone': '13812345678', ...} 结果='5678'`

一旦日志被采集到集中式系统（ELK/Loki/Splunk 等）或被导出，数据泄露面会显著扩大。

### 风险等级（为什么是“中风险”而不是“低风险”）

- 该能力是“可选开关”，不是默认开启；因此不属于必然漏洞。
- 但它是一个**非常典型且常见的脚枪**：很多团队在排查 compute 错误/脏数据时，会临时打开 debug/审计，而不一定能做到“仅在脱敏环境且严格限制采集链路”。
- 一旦发生泄露，影响往往是“批量 + 难回收”（日志保留期长、备份/转存多）。

## 目标（Proposal 的 Phase 0 结论应该能被复核）

- 默认路径下（不显式选择 full/raw 的情况下）**不应把原始字段值/结果写入日志**。
- 仍保留“需要时能看全量”的调试能力，但必须是显式、可审计、可回滚的启用方式。
- 不改变 `yaml_dsl compute` 的语义与性能边界（除非显式启用审计）。
- 兼容约束：`src/scalim/` 运行时代码保持 Python 3.6 兼容。

## 方案候选

### 方案 A：直接把 `default_audit_callback` 改为脱敏实现（raw 版本改名）

做法：

- 将当前 `default_audit_callback` 的行为改为调用 `redacted_audit_callback`（或直接复制其实现）。
- 把现有“记录原始值”的实现改名为 `unsafe_audit_callback` / `debug_full_audit_callback`（名称必须明确风险）。

优点：

- 立刻降低误用概率：用户“跟着名字用默认”时也不会泄密。
- 对运行时没有额外成本（只有启用 audit_callback 才会运行）。
- 改动小、上线快。

缺点：

- 若已有外部调用方依赖 `default_audit_callback` 的“全量输出”，行为会变化（但目前仓内未见引用；仍需在 release note/变更记录里注明）。

性价比：

- 高：以最小改动显著降低泄密概率。

### 方案 B：保持函数不动，但提供更强的“审计模式”入口（推荐）

做法：

- 为 `SecureComputeEngine` 增加更明确的配置形态，例如：
  - `audit_mode: Literal["none", "redacted", "full"] = "none"`
  - 或提供 `build_secure_compute_engine(audit_mode=...)` 统一创建入口（仓内所有创建点都走这个函数）。
- `audit_mode="redacted"` 时使用 `redacted_audit_callback`；`full` 时才允许 raw 日志。
- 在 `full` 模式下：
  - 额外输出显式告警（例如首次启用时 emit 一个 `WARNING`），提示“可能包含 PII，生产禁用”。
  - `full` 模式 MUST 额外要求显式“解锁条件”（例如环境变量 `SCALIM_ALLOW_UNSAFE_COMPUTE_AUDIT=1`）；未解锁时请求 `full` MUST fail-fast（避免误用/静默泄露）。
  - 可选增加“字段白名单/黑名单”或“最大长度截断”降低爆炸性泄露。

优点：

- API 意图更明确：通过 `audit_mode` 把风险显式化，可在代码评审/静态扫描时识别。
- 易于在上层统一做“生产环境禁止 full”之类的部署治理（例如只允许 CI/dev 设置）。

缺点：

- 实现与迁移成本略高：需要调整所有 `SecureComputeEngine()` 创建点（当前至少：`security.py:786`、`parsers/outputs.py:249`、`runtime_linking.py:426`、`conversion.py:36`、`output_composition_yaml.py:718`）。
- 需要补测试覆盖：确保默认行为不变、模式切换正确。

性价比：

- 高（中等成本，收益长期）：这是“把脚枪变成显式开关”的治理型改进。

### 方案 C：只做文档/注释，不改代码（不推荐）

优点：

- 零代码改动。

缺点：

- 对误用没有约束力；泄露事件往往不是“缺文档”，而是“临时排障时来不及想”。

性价比：

- 低。

## 推荐方案

推荐 **方案 B** 作为最终方向（把审计分级做成显式 API），并在 Phase 0 里先做一个最小可落地的切片：

1) 先落地“`audit_mode` / `build_secure_compute_engine`”这类显式入口，默认仍为 `none`；  
2) 同时把 `default_audit_callback` 的命名/行为调整为“安全默认”（可选叠加方案 A 的改名以进一步降低误用）。
3) 对 `audit_mode=full` 增加统一的显式解锁条件（本地/CI 标准一致），未解锁时请求 full 直接 fail-fast。

理由：

- 方案 B 能从机制上解决误用问题，而不仅仅是“换个默认”；
- 仍然保留 full 调试能力，但把风险显式化，便于治理与审计。

## 代价/收益（性价比拆解）

- 代码改动量：中（需要收敛 engine 创建入口 + 少量测试）。
- 行为变更风险：低（默认仍是 `none`；只有启用审计时才影响）。
- 安全收益：高（显著降低日志泄密概率；也降低“无意扩散 PII”风险）。
- 性能影响：低（默认无审计；`redacted` 模式下每次 compute 增加 hash/sort 的常数开销）。

## 验证建议（QA 口径）

- 单元测试：
  - `audit_mode=none` 时不调用 callback；
  - `audit_mode=redacted` 时日志 payload 不包含原始值（可用 sentinel 值断言不出现在格式化字符串中）；
  - `audit_mode=full` 时明确包含原始值（且仅此模式）。
- 文档/门禁（可选）：
  - 在 `just quick-qa` 或专项脚本中扫描 `default_audit_callback`/`full` 模式的使用点，要求显式 allow（防止回归误用）。
