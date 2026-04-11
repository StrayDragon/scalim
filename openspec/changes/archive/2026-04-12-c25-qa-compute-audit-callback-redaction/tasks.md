## 1. 引入显式 audit mode（安全默认 + 显式 full）

- [x] 1.1 在 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/security.py` 为 `SecureComputeEngine` 增加显式审计模式入口（例如 `audit_mode: none|redacted|full` 或 `build_secure_compute_engine(audit_mode=...)`），默认 MUST 为 `none`
- [x] 1.2 `redacted` 模式 MUST 使用脱敏审计（不记录字段值/结果原文）；`full` 模式才允许 raw 输出，并在启用时输出一次显式告警（WARNING）
- [x] 1.3 调整 helper 命名/行为以降低误用：名为 `default_audit_callback` 的 helper MUST 为安全默认（等价 redacted）；raw 版本改为显式不安全名称（例如 `unsafe_audit_callback`/`full_audit_callback`）

## 2. 迁移调用点（统一走 SSOT 入口）

- [x] 2.1 迁移仓内 `SecureComputeEngine()` 创建点（至少包含 `runtime_linking.py` / `output_composition_yaml.py` / `conversion.py` / `parsers/outputs.py` / `security.py` 内 factory）统一走 audit_mode/构建入口，避免各处手工传 callback 造成漂移
- [x] 2.2 保持默认行为不变：未显式启用审计时不产生额外日志/开销

## 3. 测试（防泄密口径 + 显式 full）

- [x] 3.1 更新 `tests/yaml_dsl/test_security_engine.py`：覆盖 `audit_mode=none` 不调用回调、`redacted` 不包含原始值、`full` 才包含原始值
- [x] 3.2 增加一条防回归断言：`default_audit_callback` 在启用时 MUST 不输出原始字段值/结果（安全默认）

## 4. 规范同步与验收门禁

- [x] 4.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/field-compute/spec.md` 中 “compute audit callback MUST support redaction” 要求，补充 `none|redacted|full` 的治理语义与显式 full 约束
- [x] 4.2 运行 `just openspec-check` 校验 OpenSpec 工件
- [x] 4.3 运行 `just quick-qa-only-py`（或 `just qa`）作为最终验收
