## Context

c65 将派生输出指纹从 SHA-1 迁移到 SHA-256，`output_composition.py` 已完成迁移，但 `derived_outputs.py` 中的 `fingerprint_for_meta` 仍使用 SHA-1。该函数生成稳定的元信息指纹用于对拍/诊断，不涉及安全签名，但保持一致性和消除安全审计噪音仍然有价值。

约束：
- `src/scalim/` 保持 Python 3.6 兼容（`hashlib.sha256` 在 3.6 可用）
- 指纹值是 **BREAKING** 变更：长度从 40→64 hex chars

## Goals / Non-Goals

**Goals:**
- 完成 SHA-1→SHA-256 的全面迁移
- 消除 `# noqa: S324` 标记
- 更新相关测试基线

**Non-Goals:**
- 不引入可配置的哈希算法选择
- 不提供旧指纹到新指纹的迁移工具

## Decisions

### 1) 直接替换 `hashlib.sha1()` 为 `hashlib.sha256()`

一行修改。`fingerprint_for_meta` 的调用者不对指纹格式做解析（仅用于相等比较和日志），因此长度变化不影响逻辑。

### 2) 更新测试基线

包含 `fingerprint_for_meta` 返回值的测试/快照需要更新期望值。搜索模式：`fingerprint_for_meta` 的 assert 和 snapshot fixtures。

## Risks / Trade-offs

- **BREAKING**：任何外部系统/脚本依赖 meta 指纹长度为 40 的假设将失效。通过 change log 明确标注。
- 收益：消除安全审计噪音，与 `output_composition` 指纹一致。

## Migration Plan

- 修改 `derived_outputs.py`：`sha1()` → `sha256()`，移除 `# noqa: S324`
- 全局搜索 `fingerprint_for_meta` 的测试引用，更新期望值
- 验证：`just qa`

## Open Questions

- 无。
