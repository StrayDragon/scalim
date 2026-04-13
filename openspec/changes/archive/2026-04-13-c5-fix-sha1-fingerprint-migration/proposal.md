## Why

c65 变更的设计意图是将所有派生输出指纹从 SHA-1 迁移到 SHA-256。`output_composition.py` 的迁移已完成，但 `execution/derived_outputs.py` 中的 `fingerprint_for_meta` 仍使用 `hashlib.sha1()`（带 `# noqa: S324`）。SHA-1 已被密码学界视为不安全（碰撞攻击已实际可行），且保留混用 SHA-1/SHA-256 会造成指纹长度不一致（40 vs 64 hex chars），增加对拍/诊断时的混淆风险。

## What Changes

- 将 `derived_outputs.py` 中 `fingerprint_for_meta` 的 `hashlib.sha1()` 替换为 `hashlib.sha256()`。
- 移除对应的 `# noqa: S324` 标记。
- **BREAKING**：meta 指纹值长度从 40 字符变为 64 字符。
- 更新依赖该指纹格式的测试期望值。

## Capabilities

### New Capabilities

### Modified Capabilities
- `derived-outputs`: meta 指纹算法从 SHA-1 变更为 SHA-256，指纹长度从 40 增加到 64 hex 字符。

## Impact

- 文件：`src/scalim/execution/derived_outputs.py`（`fingerprint_for_meta` 函数）。
- **BREAKING**：依赖 meta 指纹的审计数据/对拍快照需要更新基线。
- 安全审计工具（如 bandit）将不再对此文件报 S324。
