# `object` 类型标注治理

## 目的

`scripts/check-object-type.py` 默认扫描 `src/scalim/` 与 `scripts/` 中类型标注里的 `object`,把动态边界变成可审阅基线,推动用更精确的类型(`Protocol` / `TypedDict` / 具体类型 / 窄化后的别名)替代裸 `object`/`Any`.

**`tests/` 不在默认扫描范围**(测试注解噪音故意忽略;不参与门禁与日常报告).需要时再显式传入路径.

## 当前姿态(基线)

- **已进入** `just quick-check` / `qa` 阻断门禁(默认扫描根 `src/scalim` + `scripts`; `tests/` 不扫).
- 扫描器覆盖: 模块级函数、**类方法 / 嵌套类 / 嵌套函数** 的参数与返回标注、类字段 `AnnAssign`、以及 `X = object` 别名.
- 当前量级(默认根): **`block=0`** / **`allow=2`**(仅 `typedefs.py` 的 `CellValue`/`RuntimeValue` SSOT 别名).
- 扫描器可按需运行;报告写入 `.tmp/artifacts/`(勿提交).
- `scripts/` 与 `vendor/` 命中记为 `whitelist`,不参与 `--check` 阻断.
- 运行时新增 `object` 逃逸走 **quick 路径**(改类型 / 有理由 pragma);**仅当**需要改 `llmanspec` MUST/SHALL 时再开 `SDD` propose.

## 例外 pragma

与其它治理门禁一致,确属必要的动态边界须显式标注并写清原因:

- 行级: `# pragma: allow-object <reason>`
- 文件级: `# pragma: allow-object-file <reason>`

不要为了过门禁批量加空理由 pragma;优先改类型.

## 常用命令

```bash
just report-object-type
just check-object-type
uv run python scripts/check-object-type.py --json
uv run python scripts/check-object-type.py --check --quiet
```

- `report-object-type`: 打印报告(非阻断).
- `check-object-type`: `--check` 模式;有 `block` 时非 0;已接入 `quick-check`.
- `--quiet` 与其它严肃检查一致: 通过时静默 stdout;失败仍报告.

## 维护方向

1. 保持默认扫描 `block=0`;新增代码勿再引入裸 `object` 标注.
2. 公共 API / 跨边界入参优先 `Protocol` 或 `Enum` SSOT,而不是 `object`.
3. `tests/` 仍故意不扫;勿为清测试噪音改默认根.
