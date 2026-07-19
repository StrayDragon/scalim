# `object` 类型标注治理

## 目的

`scripts/check-object-type.py` 扫描 `src/scalim/`、`tests/`、`scripts/` 中类型标注里的 `object`,把动态边界变成可审阅基线,推动用更精确的类型(Protocol / TypedDict / 具体类型 / 窄化后的别名)替代裸 `object`/`Any`.

## 当前姿态(基线)

- **不进入** `just qa` / `quick-check` 阻断门禁,直到 `block` 可收敛到可维护规模(当前量级约数百处 `block`).
- 扫描器可按需运行;报告写入 `.tmp/artifacts/`(勿提交).
- `scripts/` 与 `vendor/` 命中记为 `whitelist`,不参与 `--check` 阻断.
- 嵌套 class 方法等边界的扫描覆盖仍可能偏松;完整清债与扫描修正应走独立 SDD 变更,不要借一次 PR 硬接门禁.

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

1. 先修扫描覆盖缺口(嵌套方法等),再按域(workflow / yaml_dsl / tests)分批收窄.
2. 公共 API / 跨边界入参优先 Protocol 或 Enum SSOT,而不是 `object`.
3. `block→0` 且扫描可信后,再评估是否把 `check-object-type` 接入 `quick-check`.
