## 1. Output meta/audit 安全落盘

- [x] 1.1 为 `output_composition` 增加 error_message 的“安全摘要 + hash + 显式开关完整 message”策略并写入 meta/audit
- [x] 1.2 补齐 `tests/test_output_composition.py` 覆盖默认安全摘要与显式开启完整 message 两种路径

## 2. Excel 公式注入与并发写出保护

- [x] 2.1 在 `sink_excel` 中实现 Excel 公式注入防护(escape/allow 两种模式),默认使用 escape
- [x] 2.2 增加 `tests/test_sinks_excel_additional.py`(或新测试)验证 escape/allow 行为(读取单元格公式/字符串)
- [x] 2.3 为 Excel/Workbook 写出提供低成本并发写出保护(可选 lock 或 fail-fast),并补齐测试覆盖

## 3. 资源/内存风险告警与文档化

- [x] 3.1 `DerivedGroupBySpec.max_groups=0` 时输出明确 warn(一次性)并补齐测试
- [x] 3.2 调整 rows 绑定缓存实现: 避免将完整 `batch_rows` 存入长生命周期 cache;同时更新日志与可复用文档(含 `$rows.cache_mode` 指引)

## 4. QA 门禁: py36 检查强制 Docker

- [x] 4.1 修改 `justfile` 移除无 docker 时的兜底检查,强制 docker 不可用时 fail-fast 并给出安装指引
- [x] 4.2 增加回归护栏测试/脚本,确保未来不会被改回“warn + fallback”模式

## 5. Streaming 回归护栏

- [x] 5.1 为 rows 绑定屏障 + 行释放协调器补齐关键行为不变测试用例(不依赖私有实现细节)

## 6. 验证

- [x] 6.1 运行 `just qa` 并修复本变更引入的失败(不处理无关问题)
