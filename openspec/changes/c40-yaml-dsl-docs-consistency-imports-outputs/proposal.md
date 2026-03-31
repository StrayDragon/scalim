## Why

当前 YAML DSL 的实现与用户侧文档/示例存在多处漂移,典型表现为:

- 文档仍描述旧的 imports/$import 限制与路径语义,与当前实现的相对路径 + allow-roots + alias/presets 机制不一致
- 文档仍把 `outputs.*.container` 描述为 `workbook/csv` 双形态,但实际 parser 仅接受 `csv`(Excel 输出路径已迁移到 `resources.books` + `outputs.*.to`)
- 部分校验错误信息/迁移提示仍给出已无效的示例(例如 `container.type: workbook`),容易误导作者
- 相关“技能参考材料/升级文档”中仍残留 `container.type: workbook` / `container.sheet` 等已移除语法,会持续误导新配置与迁移路径(需要显式修正或标记为历史文档)

这会直接降低 YAML authoring 的可预期性: 用户按文档写出的 YAML 可能在 validate/compile 阶段被拒绝,或在排障时走错迁移路径。

## What Changes

- 更新 docs SSOT(手写页)以与当前实现一致:
  - imports/$import 的路径解析基准、允许/拒绝的形态、以及 roots/alias 的真实边界
  - `outputs.*.container` 仅作为 CSV 文件输出 authoring surface; Excel 输出仅通过 `resources.books` + `outputs.*.to`
- 更新 capability matrix 与 user guide 中相关段落/示例,避免出现 `workbook` container 示例或过期表述。
- 更新 validator 中遗留的迁移提示文案,避免给出已无效的示例 YAML。
- 更新技能参考材料(非 docs-site)中明确错误的 DSL 示例,避免继续传播已移除语法(仅修正“示例/迁移提示”,不重写历史叙述)。
- 保留现有“负例 fixture”(例如 `container.type: workbook`)作为明确的拒绝测试,但不得在用户文档中作为示例出现。

> 文档治理边界: 不手改任何 `*.gen.*` 与 injected blocks. 修改 `docs/doc/**/*.md` 的 SSOT 后运行 `just gen-docs` 刷新生成物,并通过 `just docs-drift-check`/`just qa` 验收。

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `docs-site`: YAML DSL 手册页必须与实现保持一致,不得在手册页/示例中呈现已移除语法(例如 workbook container),并对 imports/$import 给出与实现一致的路径语义描述。

## Impact

- 文档与提示: 作者将获得与实现一致的 guidance,降低“按文档写 YAML 但 validate 失败”的概率。
- 回归: 需要更新/补充 docs 相关的 drift checks 与示例一致性断言(如果已有)。

## Sequencing

- 建议在 `c30`(诊断路径口径统一) 与 `c20`(校验集合收敛)落地后再集中修正文档/示例,避免文案与回归截图/错误路径再次漂移。
