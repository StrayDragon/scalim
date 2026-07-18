# tasks: c15-tabular-bus-object-sink-accept-precheck

## 0. Evidence（共享）

- [x] 0.1 将 MVP probe 脚本落到本 change `evidence/`（输出默认 `.tmp/...`）
- [x] 0.2 写入 `evidence/README.md` + 结果摘要（可共享；原始 JSON 可再跑）

## 1. Specs / 合约

- [x] 1.1 修改 `workflow-intermediate-store`：ROWS 细胞 = object；禁止静默 `str()`；结构校验保留
- [x] 1.2 修改 `workflow-shared-output-containers`：xlsx 管道原样透传（不把 FieldValue 闭集当总线门禁）
- [x] 1.3 扩展 `output-sink-contracts`：sink accept set + opt-in 预检（默认关）+ 写出失败不 promote 最终半成品
- [x] 1.4 `llman sdd validate c15-tabular-bus-object-sink-accept-precheck --strict --no-interactive`

## 2. ROWS 总线放宽

- [x] 2.1 `InMemoryRows` / `InMemoryRowsSink` 去掉 `FIELD_VALUE_TYPES` 运行时门禁；保留结构校验
- [x] 2.2 注解/`typedefs`：ROWS 细胞与 `FieldValue` 解耦；`FieldValue` 文档化为 Excel 推荐集
- [x] 2.3 同步 YAML `_ensure_field_value` 策略决策：derived/literal **保留** FieldValue 窄校验（与 ROWS object 解耦）
- [x] 2.4 更新 `tests/sinks/test_sink_rows.py` 等：接受 `np.datetime64`/`object`；仍禁止静默 `str()`

## 3. Sink accept set + opt-in 预检

- [x] 3.1 为 Excel（及 CSV 语义）声明 accept set / 谓词（基于探测，不夸大）
- [x] 3.2 Python opt-in 预检开关（`SinkTypePrecheck` SSOT）；默认关闭；MUST NOT YAML
- [x] 3.3 启用时：写入前按目标 sink accept set TypeError；错误含 field/type/sink
- [x] 3.4 测试：默认路径 `np.datetime64` 晚失败于 Excel；opt-in 早失败

## 4. 写出失败清理（MVP）

- [x] 4.1 回归/补强：Excel/CSV save|replace 失败 → 无最终半成品 + temp best-effort 清理
- [x] 4.2 异常路径 `discard()`，`__exit__` 不再盲目 `close()` promote
- [x] 4.3 workflow：最终 publish 失败不留半残最终文件；staging `keep_on_failure` 默认行为文档化（本 change 不改默认）

## 5. Docs / 门禁

- [x] 5.1 agent upgrade：`2026-07-18-tabular-bus-object-sink-accept-precheck.md` + `just gen-docs`
- [x] 5.2 相关单测绿（sink rows / c15 precheck / temporal / excel regressions / csv）
- [x] 5.3 `llman sdd validate c15-... --strict --no-interactive` 与定向 pytest 绿
