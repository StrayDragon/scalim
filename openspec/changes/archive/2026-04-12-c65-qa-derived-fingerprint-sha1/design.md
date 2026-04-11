## Context

`OutputComposition` 的派生输出（`DerivedOutputTargetSpec`）会在 meta/audit 中写入一个“派生聚合指纹”（fingerprint），用于：

- 对拍/复现：同一派生定义在不同运行中应得到相同 fingerprint
- 诊断归因：按 fingerprint 聚合派生输出相关错误（audit sheet、日志、下游消费）

当前实现使用 `hashlib.sha1()` 计算 fingerprint，并通过 `# noqa: S324` 压制安全 lint（S324 通常认为 SHA1 不适合安全用途）。

这里的 fingerprint 并非加密/签名用途，而是“稳定标识符”。工程上的关键矛盾在于：

- 若切换算法（例如 sha256），会导致所有 fingerprint 值变化，从而破坏对拍/聚合等稳定性；
- 若保留 sha1，需要把其用途与边界显式化，避免被误解为安全相关 hash，并降低安全审计沟通成本（至少做到“有意且有注释”）。

约束：

- Python 3.6/3.10 均支持 sha1/sha256；真正风险在于 fingerprint 输出稳定性，而不是 Python 版本兼容性
- fingerprint 进入 meta/audit，属于“对外可见的稳定输出”的概率较高，变更需谨慎

## Goals / Non-Goals

**Goals:**

- 切换 fingerprint 算法到 `sha256` 并移除 `S324` 治理摩擦
- 明确 fingerprint 的用途边界：仅用于稳定标识符/对拍与归因，不用于安全目的
- 保持对同一输入的确定性（同一 payload 得到同一 fingerprint）

**Non-Goals:**

- 不做双写/版本化迁移（接受 fingerprint 值变化属于显式 breaking）
- 不引入新的对外配置字段（仍使用现有 `derived.<id>.fingerprint` 字段）

## Decisions

### 1) Phase 0 切换 fingerprint 算法到 sha256（方案 B，一步到位）

采用一步到位的治理策略：

- 将 `hashlib.sha1()` 替换为 `hashlib.sha256()` 生成 hex digest
- 移除 `# noqa: S324`
- 在实现处补充明确注释：
  - 该 hash 仅用于稳定 fingerprint（非安全用途）
  - 不用于签名/认证/加密
  - 本次变更属于显式 breaking：fingerprint 值将变化（长度也将从 40 变为 64）

同时补齐单测覆盖 fingerprint 的稳定性与对输入变化的敏感性，并更新任何对拍/快照用例，作为回归护栏。

### 2) 将算法/格式变更视为“显式 breaking 输出”

fingerprint 字段进入 meta/audit，属于“对外可见输出”。后续若再变更算法或 payload 归一化规则：

- 变更 MUST 显式声明其兼容性影响（breaking）
- 若必须兼容迁移，则应通过新增 v2 字段等方式实现（不应在同一字段内静默变更）

本 change 选择 breaking 路线（sha256），并把“未来再变更”作为显式治理要求写入规范与任务清单。

## Risks / Trade-offs

- **保留 S324 抑制**：仍需要 `# noqa: S324`，但通过显式注释与规范化说明让其成为“有意例外”而不是“遗留脚枪”。
- **未来演进成本**：若后续决定升级算法，仍需处理对拍/下游聚合的迁移成本；提前在规范中明确策略可降低临时决策风险。

## Migration Plan

- Phase 0：补齐注释 + 单测护栏 + delta spec 明确“非安全用途 + 演进策略”
- 后续（可选）：若要升级算法，单独开 change 实施 B 或 C，并配套对拍/下游迁移说明

## Open Questions

- 无。
