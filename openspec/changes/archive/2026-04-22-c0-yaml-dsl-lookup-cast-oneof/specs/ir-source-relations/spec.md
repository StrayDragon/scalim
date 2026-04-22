## MODIFIED Requirements

### Requirement: lookup_key 与 lookup_cast/诊断
系统 SHALL 使用 `to_field` 或目标 source 的 `key` 作为 lookup key;当 `to_field` 为非 key 字段时,loader 返回映射的 key 必须匹配该字段.
系统 SHALL 在 lookup 前对 `from` 值应用 `lookup_cast`(step 级优先,缺省使用 source 级),支持 `auto`/`int`/`str`/`sep_first`,多字段关联逐字段应用并在任一字段缺失或转换失败时忽略该键.
`auto_normalize_key` 规则: None/NaN->None,float->None(触发采样诊断告警),bool->0/1,int/str 保持,Decimal 可整数化则转 int 否则回退 `auto_str_normalize`,其他类型回退 `auto_str_normalize`.
诊断告警文案应提示配置 `lookup_cast`/`value_cast` 或调整 relation 定义,并复用跨模块统一常量.

#### Scenario: step 级 lookup_cast
- **WHEN** step 配置 `lookup_cast: {sep_first: {sep: ","}}` 且 `from` 为 "1,2,3"
- **THEN** lookup key 为 "1"(再按 auto_normalize_key 规则归一化)

#### Scenario: 浮点被拒绝
- **WHEN** `lookup_cast: {auto: {}}` 且外键值为 123.0 或 12.34
- **THEN** 归一化结果为 None 且该键被忽略,并触发诊断告警事件

#### Scenario: 多字段缺失
- **WHEN** 多字段关联中任一 from_field 为 None
- **THEN** 该键不参与关联查找
