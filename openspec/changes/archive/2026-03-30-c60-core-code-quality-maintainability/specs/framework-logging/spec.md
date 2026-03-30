## ADDED Requirements

### Requirement: runtime MUST NOT mix print with structured logging

系统 MUST 将 runtime 的用户可见诊断输出统一为结构化 logger 输出（例如 `loggingx` 的 prefix + kv）,并禁止在 runtime 代码路径中直接使用 `print(...)`.

#### Scenario: print usage in runtime fails fast
- **WHEN** 在 `src/scalim/` 的 runtime 路径中出现 `print(...)`
- **THEN** gate MUST fail-fast 并提示迁移到结构化 logger

