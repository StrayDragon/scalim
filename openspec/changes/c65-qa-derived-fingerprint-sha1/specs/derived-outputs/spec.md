# derived-outputs (delta) Specification

## MODIFIED Requirements

### Requirement: meta/audit 的稳定指纹与结构化审计
系统 MUST 为每个 derived target 生成稳定聚合指纹(不包含 callables/环境相关对象),并写入 meta sheet.

系统 MUST 满足:
- meta 中 MUST 写入: `derived.<target_id>.fingerprint`
- 当触发护栏失败/截断/冲突等情况时:
  - 系统 MUST 写入结构化 audit 行
  - audit 行 MUST 仅包含: 目标标识/配置指纹/计数统计/稳定的 message hash 等脱敏信息
  - audit 行 MUST NOT 泄露明细行内容与聚合 key 的具体值

治理与兼容约束（新增）：

- `fingerprint` 的用途 MUST 明确为“稳定标识符/对拍与归因”，不得被用于签名、认证、加密等安全目的
- 实现 MUST 使用 `sha256` 生成 fingerprint（hex digest），以避免 `sha1`/`S324` 治理摩擦并提升环境可接受性（例如 FIPS）
- 若未来需要变更 fingerprint 算法或输出格式（含 payload 归一化规则），变更 MUST 显式声明其兼容性影响，并且 MUST 选择以下策略之一：
  - BREAKING：明确告知 fingerprint 将变化并更新对拍/下游聚合口径
  - 版本化/双写：保留旧 fingerprint 并新增 v2 字段供下游渐进迁移

#### Scenario: 写入派生聚合指纹到 meta
- **WHEN** 运行包含 derived target
- **THEN** 系统 MUST 在 meta 中写入 `derived.<target_id>.fingerprint`
