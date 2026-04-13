## 1. Implementation

- [x] 1.1 在 `src/scalim/execution/derived_outputs.py` 中将 `fingerprint_for_meta` 的 `hashlib.sha1()` 替换为 `hashlib.sha256()`，并移除对应 `# noqa: S324`
- [x] 1.2 全局搜索 `fingerprint_for_meta` 及依赖 40 字符指纹的断言/快照，更新期望值为 64 字符 SHA-256 形式（无测试直接断言指纹值）

## 2. Verification

- [x] 2.1 Run `just qa` / `just test-gate` to verify
- [x] 2.2 Run `just openspec-check` to validate artifacts
