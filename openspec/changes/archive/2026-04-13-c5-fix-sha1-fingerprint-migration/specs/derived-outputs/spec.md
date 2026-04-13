# derived-outputs (delta) Specification

## ADDED Requirements

### Requirement: 派生输出 meta 元信息指纹算法（SHA-256）

`execution/derived_outputs` 中为 meta 生成的稳定元信息指纹（`fingerprint_for_meta` 或等价实现）MUST 使用 `hashlib.sha256()` 计算十六进制摘要。

实现 MUST NOT 使用 `hashlib.sha1()` 计算该指纹，且 MUST NOT 为此依赖 `# noqa: S324` 抑制 bandit 告警。

该指纹字符串为 **BREAKING** 变更：由 SHA-1 的 40 个十六进制字符变为 SHA-256 的 64 个十六进制字符；依赖固定长度或旧摘要值的审计基线、快照与外部脚本 MUST 更新。

#### Scenario: meta 指纹为 SHA-256 形式

- **WHEN** 为派生输出 meta 计算元信息指纹
- **THEN** 返回的 digest MUST 为 64 字符的小写十六进制字符串（SHA-256）
- **AND** MUST NOT 再产生 40 字符的 SHA-1 形式摘要

#### Scenario: 测试与基线随迁移更新

- **WHEN** 测试或快照断言 `fingerprint_for_meta` 的返回值或指纹长度
- **THEN** 期望 MUST 与 SHA-256 输出一致
