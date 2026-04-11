## Context

`yaml_dsl` 支持派生字段 `compute` 表达式：通过 `SecureComputeEngine` 做 AST allowlist 校验后再执行 `eval`。为便于排障与可观测性，`SecureComputeEngine` 提供了可选的审计回调接口 `audit_callback(expression, field_values, result)`，用于在每次求值时记录诊断信息。

当前仓库同时提供：

- `default_audit_callback(...)`：将 `field_values` 与 `result` 的原始内容写入 debug log（注释提示可能包含 PII）。
- `redacted_audit_callback(...)`：仅记录表达式 hash、字段名列表与结果类型（脱敏）。

风险在于：一旦业务侧/集成侧启用 `default_audit_callback`，就可能把真实数据行的原始字段值与计算结果写入日志。日志系统往往更广泛可见、更难回收，属于典型“脚枪”型风险；且从命名上 `default_audit_callback` 很容易被误认为“推荐默认值”直接使用。

约束：

- `src/scalim/` 运行时代码保持 Python 3.6 兼容
- 默认情况下不引入额外性能开销（未显式启用审计时不做额外计算/格式化）

## Goals / Non-Goals

**Goals:**

- 在“未显式选择 full/raw”的默认路径下，compute 审计 MUST 不记录原始字段值/原始结果内容，避免日志泄密
- 仍保留 full/raw 调试能力，但必须是显式、可审计、可回滚的启用方式
- 将审计模式收敛为清晰的 API 形态，避免调用点自行拼装 callback 造成不一致与误用

**Non-Goals:**

- 不改变 `yaml_dsl compute` 的语义（仅在显式启用审计时增加日志输出）
- 不在本次引入复杂的 PII 识别/字段级脱敏策略（例如黑白名单/正则规则），仅先把“默认安全 + 显式 full”落地

## Decisions

### 1) 引入显式的 audit mode/统一构建入口（方案 B，Phase 0 切片）

Phase 0 采用“显式模式 + 统一入口”的治理方向：

- 为 `SecureComputeEngine` 的创建提供显式审计模式（例如 `audit_mode: none|redacted|full`），或提供 `build_secure_compute_engine(audit_mode=...)` 作为唯一构建入口
- 默认值 MUST 为 `none`：不调用任何审计回调（默认无额外开销）
- `redacted` 模式使用脱敏审计实现（不记录字段值/结果原文）
- `full` 模式才允许 raw 审计输出，并在启用时额外发出显式告警（例如首次启用时 `WARNING` 提示“可能包含 PII，生产禁用”）

该策略能把风险从“函数名选择”提升为“显式配置选择”，便于 code review/静态扫描识别并建立治理规则。

### 2) 调整 `default_audit_callback` 为“安全默认”（可选叠加方案 A 的改名）

为进一步降低误用概率：

- 将名为 `default_audit_callback` 的对外 helper 收敛为安全默认（等价 `redacted`），避免“跟着名字用 default”导致泄密
- 将当前 raw 实现改名为显式不安全的名称（例如 `unsafe_audit_callback` / `full_audit_callback`），并仅在 `audit_mode=full` 下被选用

内部调用点一律通过统一入口选择模式，避免手工传入 callback 造成不一致。

### 3) `full` 模式必须显式解锁（统一标准：本地/CI 一致）

仅靠“文档约定”不足以避免误用；因此对 `audit_mode=full` 采用统一、强约束策略：

- `full` 模式 MUST 为显式 opt-in，且必须通过额外的“解锁条件”启用（例如环境变量 `SCALIM_ALLOW_UNSAFE_COMPUTE_AUDIT=1` 或等价开关）
- 未满足解锁条件时，若调用方请求 `full`，系统 MUST fail-fast（避免静默泄露）
- 该策略不区分本地/CI：默认标准一致；需要 full 时由操作者显式打开并承担风险

## Risks / Trade-offs

- **API/迁移改动量**：需要调整仓内所有 `SecureComputeEngine(...)` 创建点以走统一入口/模式开关；但这是一次性治理成本，能降低长期误用风险。
- **外部行为变化**：若外部调用方依赖 `default_audit_callback` 的“全量输出”，改名/改行为会产生变化；需要在变更记录中明确说明，并保留 full/raw 的显式入口。

## Migration Plan

- Phase 0：引入 audit_mode/统一构建入口 + 调整 helper 命名；仓内所有创建点迁移完成并补齐单测
- 后续（可选）：增加更细粒度的脱敏策略（字段白名单/黑名单、最大长度截断）与更严格的“生产环境禁止 full”门禁

## Open Questions

- 无。
