## ADDED Requirements

### Requirement: definition MUST return ordered multi-locations with stable de-dup

当某个引用存在多个合理的 definition 候选时（例如“真实实现”与“构造/赋值点”同时可推断）,LSP server MUST 返回 **多 locations**，并满足：

- locations MUST 稳定排序（便于用户重复触发时结果不抖动）。
- locations MUST 去重（同 URI + 同 range 视为同一候选）。
- 排序规则 MUST 可测试（例如：真实实现优先于 fallback；同优先级按 path → line 排序）。

#### Scenario: multiple candidates are returned and ordered
- **GIVEN** 解析某个 Python 引用时同时得到“方法定义行”和“对象赋值行”两个候选 location
- **WHEN** 用户在引用处触发 `textDocument/definition`
- **THEN** server MUST 返回包含两个 location 的列表
- **AND** 列表中的第一个 location MUST 为“更接近真实实现”的候选（例如方法定义行）
- **AND** 返回结果 MUST 稳定（重复请求的顺序一致）
