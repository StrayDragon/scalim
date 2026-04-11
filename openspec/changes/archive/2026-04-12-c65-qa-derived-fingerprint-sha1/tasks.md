## 1. 切换 fingerprint 到 sha256（方案 B，一步到位）

- [ ] 1.1 在 `src/scalim/execution/output_composition.py` 的 `_fingerprint_for_derived_target` 将 `hashlib.sha1()` 替换为 `hashlib.sha256()` 并移除 `# noqa: S324`
- [ ] 1.2 补充明确注释：fingerprint 仅为稳定标识符（非签名/认证/加密用途）；本次变更属于显式 breaking（fingerprint 值/长度变化），需要更新对拍/下游聚合口径

## 2. 单测护栏（稳定 + 对输入敏感）

- [ ] 2.1 新增单测覆盖 fingerprint：相同输入稳定；`target_id/parts` 变化会变化；并断言写入 meta/audit 的 fingerprint 字段存在

## 3. 规范同步与验收门禁

- [ ] 3.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/derived-outputs/spec.md`，明确 fingerprint 使用 `sha256`（非安全用途）且算法/格式变更必须显式 breaking（或版本化迁移）
- [ ] 3.2 运行 `just openspec-check` 校验 OpenSpec 工件
- [ ] 3.3 运行 `just quick-qa-only-py`（或 `just qa`）作为最终验收
