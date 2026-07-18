---
depends_on: []
---

# Proposal: c15-tabular-bus-object-sink-accept-precheck

> **状态**: active（2026-07-18）。  
> **承接**: 讨论结论——`InMemoryRows` 闭集与 sink 写出约束缠在一起造成赘余；relation 只需 `Hashable`/`==`。  
> **证据 MVP**: 本目录 `evidence/`（脚本可复现）；运行产物默认写 `.tmp/evidence/rows-object-bus-mvp/`。

## Why

`c0-add-field-value-datetime` 把 openpyxl `TIME_TYPES` 纳入 `FieldValue`，并在 `InMemoryRowsSink` 对未知类型 fail-fast。这修复了「workflow 把日期 `str()` 成文本」的分裂，但把 **表格总线** 与 **某 sink（Excel）可写集合** 绑死：

- `np.datetime64`：ROWS 早死；openpyxl 也会拒——总线门禁无额外价值。
- `np.int64`：ROWS 拒；openpyxl **能写**——总线过严。
- `pd.Timestamp`：因是 `datetime` 子类而「漏过」闭集——规则不自洽。
- relation 关联键本就是 `LookupKey = Hashable`；loader 值已有 `RuntimeValue = object`。中间态再维护一份追不全的类型宇宙，ROI 为负。

产品倾向：

1. **总线不约束细胞类型**（任意 py object；只保证表结构）。
2. **按 sink 声明可接受类型集**（对齐底层库）。
3. **默认**：错误延迟到 sink write（与库行为同源）。
4. **开发 opt-in**：启动侧可按目标 sink 的 accept set 在写入前预检（体验接近今日早失败）。
5. **晚失败必须可清理**：不留下最终半成品；temp/staging best-effort 回收（RAII）。

## What Changes

1. **`InMemoryRows` / `InMemoryRowsSink`**：细胞值域放宽为 `object`；保留 header/行列结构校验；**禁止**对未知类型静默 `str()`。
2. **`FieldValue` / `FIELD_VALUE_TYPES`**：保留为 **内建 Excel 推荐/文档闭集** 与兼容别名，不再作为 ROWS 运行时门禁 SSOT。
3. **Sink accept set**：内建 Excel/CSV（及后续 sink）声明「本 sink 能接受/透传的类型」契约（基于底层库能力；MVP 以 Excel/openpyxl + CSV/`str` 为主）。
4. **Opt-in 预检**（Python SSOT，禁止 YAML knobs）：启用时在进入 sink 写出前按目标 accept set fail-fast；默认关闭。
5. **写出失败清理（MVP）**：file sink / workbook commit 失败时 MUST NOT 把半成品 promote 到最终路径；temp MUST best-effort 清理；异常路径不得因 `__exit__` 盲目成功 commit 而留下最终坏文件（对齐并收紧现有 atomic 路径缺口）。
6. **证据**：保留可复现 MVP（numpy/pandas/openpyxl/ROWS 门禁对照）；测试覆盖：ROWS 接受 `np.datetime64`/`object`；默认晚失败；opt-in 预检早失败；Excel save 失败无最终文件。

非目标（本 change）：

- 自动把 `np.datetime64`/`Timestamp` 转成 stdlib（禁止静默改写；转换须显式 adapter，另案）。
- 改 relation `key_normalization` 语义。
- 默认改 workflow `output_staging_keep_on_failure`（debug 保留 staging 仍可；最终 publish 路径不得半残）。
- pandas/parquet sink 完整类型矩阵（可声明 stub accept set，细节另案）。
- YAML 暴露 type-precheck knobs。

## Capabilities

- `workflow-intermediate-store`（ROWS 细胞 = object；改写 r88/r912）
- `workflow-shared-output-containers`（xlsx 管道「原样透传」而非 FieldValue 闭集门禁；改写 r393）
- `output-sink-contracts`（accept set + opt-in 预检 + 失败清理）

## Impact

- **Breaking（有意、窄）**：依赖「`InMemoryRowsSink` 对非 FieldValue 必 TypeError」的测试/调用方需改；依赖该早失败做业务校验的代码应改用 opt-in 预检或自行校验。
- **Compat**：既有 stdlib `FieldValue` 路径（含 naive 时间 → Excel 日期）行为不变；CSV 仍显式/`str` 语义；不恢复中间态 `str()` 补丁。
- **Perf**：去掉 ROWS 热路径上的闭集 `isinstance`；opt-in 预检默认关闭故无默认开销。
- **Ethics**: `risk_level=medium`
  - **prohibited**: 在 ROWS/中间态静默 `str()` 或去 tz；用框架伪装 openpyxl 不能写的类型为成功；把 type-precheck 放进 YAML 主线。
  - **required_evidence**: MVP probe 可复现；失败清理测试（最终路径不半残）。
  - **escalation**: 若要默认打开全局预检或自动 coerce numpy→stdlib，须另开 change 并人工确认。

## Evidence

- 共享脚本/摘要：`llmanspec/changes/c15-tabular-bus-object-sink-accept-precheck/evidence/`
- 运行输出（可丢弃）：`.tmp/evidence/rows-object-bus-mvp/`
