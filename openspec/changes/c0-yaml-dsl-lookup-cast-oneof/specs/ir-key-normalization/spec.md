## MODIFIED Requirements

### Requirement: `key_normalization` string modes MUST normalize match keys

系统 MUST 提供基于字符串的 key 规范化策略 `key_normalization=auto_str` 与 `key_normalization=force_str`.

当启用任一字符串策略时,框架内部所有”需要匹配”的 key 在进入匹配边界时 MUST 逐字段应用字符串规范化后再参与匹配.

并且字符串规范化的启用时机 MUST 遵循 cast precedence 规则(即 `auto_str` 为 fallback,`force_str` 为强制).

#### Scenario: auto_str normalizes raw int key into a stable string
- **GIVEN** raw match key 为 `1`(int)
- **WHEN** 用户启用 `key_normalization=auto_str`
- **AND** 未显式配置 cast
- **THEN** 系统 MUST 将该 key 规范化为稳定字符串 `”1”` 后参与匹配

#### Semantics: `None` vs normalize failure

- raw 为 `None` 表示”空值”: 在 relations 中 MUST 计入 null key;在 derived `group_by`/`dedup_by` 中 MUST 允许作为 key 的组成部分
- raw 非 `None` 但规范化返回 `None` 表示”无法规范化”: 在 relations 中 MUST 计入类型错误;在 derived `group_by`/`dedup_by` 中 MUST fail-fast

当需要输出错误/诊断 message 时,系统 MUST NOT 在 message 中包含 raw key 的明细值;message SHOULD 仅包含类型/字段/来源/原因等上下文信息.

#### Semantics: float keys
当 raw key 为 `float` 时:

- `NaN/inf` MUST 视为规范化失败
- 其余 float MUST 按 `auto_str_normalize` 规则规范化为稳定字符串(整数 float 去除小数部分;非整数 float 使用稳定格式化)

注意: 该行为与 relations 的 `lookup_cast: {auto: {}}`(会拒绝 float) 不同;启用 `key_normalization=auto_str` 或 `key_normalization=force_str` 表示用户接受按字符串语义做 key 匹配的风险.

#### Semantics: multi-field keys
当 key 为多字段复合键时(例如 `Tuple[object, ...]`):

- 系统 MUST 对每个组成字段逐字段应用 `auto_str_normalize`
- 系统 MUST 将规范化后的结果组成 `Tuple[str, ...]` 作为 match key
- 任一组成字段 raw 为 `None` → relations MUST 视为 `null_key`
- 任一组成字段 raw 非 `None` 且规范化失败 → relations MUST 视为 `type_error`(derived MUST fail-fast)

#### Semantics: key collisions after normalization
当多个不同 raw key 规范化到同一个稳定字符串 key 时:

- derived outputs 的 `group_by`/`dedup_by` 语义为“合并”: 这是该能力的预期行为(按规范化 key 合并)
- relations 在构建“需要匹配的 mapping 的规范化视图”时的 collision 处理,见下方 requirement(`relations mapping collisions after normalization...`),并保持 redacted
