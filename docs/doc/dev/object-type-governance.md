# `object` 类型标注治理

## 目的

`scripts/check-object-type.py` 扫描 `src/scalim/`、`tests/`、`scripts/` 中类型标注里的 `object`,把动态边界变成可审阅基线,推动用更精确的类型(`Protocol` / `TypedDict` / 具体类型 / 窄化后的别名)替代裸 `object`/`Any`.

## 当前姿态(基线)

- **不进入** `just qa` / `quick-check` 阻断门禁,直到 `block` 可收敛到可维护规模.
- 扫描器覆盖: 模块级函数、**类方法 / 嵌套类 / 嵌套函数** 的参数与返回标注、类字段 `AnnAssign`、以及 `X = object` 别名.
- 当前量级(完整扫描后,约数): **`src/scalim block=0`** / **`tests block≈356`** / **`total≈364`** / **`allow=2`**(batch7 清空 `src/scalim`; 仅 `typedefs.py` 保留 `CellValue`/`RuntimeValue` SSOT 别名).
- 扫描器可按需运行;报告写入 `.tmp/artifacts/`(勿提交).
- `scripts/` 与 `vendor/` 命中记为 `whitelist`,不参与 `--check` 阻断.
- 分批清债走 **quick 路径**(直接改类型 / 加有理由的 pragma);**仅当**需要改 `llmanspec` MUST/SHALL 时再开 `SDD` propose. **不要**在 `block` 仍高时接入 `quick-check`.

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
- `check-object-type`: `--check` 模式;有 `block` 时非 0. **当前未接入** `quick-check`,仅供本地/专题清债使用.
- `--quiet` 与其它严肃检查一致: 通过时静默 stdout;失败仍报告.

## 清债方向(后续)

1. 扫描覆盖已按类方法/嵌套补齐;按热点文件(见 `just report-object-type`)分批收窄.
2. 公共 API / 跨边界入参优先 `Protocol` 或 `Enum` SSOT,而不是 `object`.
3. `block` 降到可维护规模且扫描可信后,再评估是否把 `check-object-type` 接入 `quick-check`.
