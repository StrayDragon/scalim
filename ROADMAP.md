# ROADMAP

> 维护策略：运行库只支持「仍在官方支持期」的 CPython 窗口；旧版本线冻结后仅安全修复，旧 fork 可基于冻结线自行迭代。

## 版本线

| 线 | 状态 | 说明 |
|---|---|---|
| 0.10.x | legacy 冻结 | Python 3.6 兼容的最后一主线；仅安全修复；旧 fork 迭代基于此线 |
| 0.11 – 0.19 | 保留号段 | 不使用 |
| 0.20.x | **现代化清理线** | 全部清理工作集中在**单一 0.20.0 统一发布**；0.20.x 后续 patch 仅修 bug |
| 1.0.0 | 目标 | API 冻结 + 支持策略承诺，正式发布 |

## Python 支持策略

- 支持窗口 = **3.10 / 3.11 / 3.12 / 3.13 / 3.14**（floor 3.10，与现行 CI 基线一致）。
- 依据：企业存量大量使用 3.10；同行框架（Airflow / Prefect / Dagster / Kedro / dbt-core 等，2026-09 调研）当前也全部支持 3.10。保留 3.10 是有意的采用面选择，弃用节奏与上游 EOL 解耦、按采用面决定。
- 已知代价（按 ratchet 逐步偿还）：`StrEnum`（3.11+）、`Self`/`override`（3.11+/3.12+）暂不能改用 stdlib → StrEnum backport 迁入 `_internal/`（floor≥3.11 时删）、`typing-extensions` 保留（仅 `Self`/`override`，pin `>=4.4`）。其余 3.6 兼容层（`dataclassesx` / `typing_extensionsx` / py36 门禁）全部照删。
- CI：matrix 各支持版本只跑 py-only 套件 `just check-only-py`；最新版额外跑全量 `just qa` 兜底（frontend / examples / notebooks coverage）。

## 0.20.0 — 现代化统一发布（单版本 · 分阶段提交）

> 不发中间版本。三个 Stage 在同一开发周期内按序完成，以清晰的 commit 边界分割（每个 Stage 对应独立 SDD change 分支），Stage 门禁全绿后合入；版本号在发布时统一 bump 一次。

### Stage A — 现代基线

- `requires-python >= 3.10`；删除 3.6 时代兼容层：`dataclassesx` → stdlib、`typing_extensionsx` → stdlib `typing` + `typing_extensions`（仅 `Self`/`override`，pin `>=4.4`）；codemod + ruff `UP` autofix（target py310，覆盖 `list[]` / `X | None` 全部改写）。
- `StrEnum` backport 从 `vendor/compact` 迁入 `_internal/strenum.py`（floor 3.10 仍需；floor≥3.11 时删除）。
- CI matrix 调整为 [3.10 … 3.14] + `check-only-py` / `qa` 分层（见上；可用 [3.10, 3.14] 边界对裁剪 CI 耗时）。
- 删除 py36 门禁（docker checks + scripts）与 `vendor-legacy-sync`（`just sync-project-vendors` 及对应 spec 退役）。
- spec 同步修订（governance-module-organization / vendor-* / yaml-dsl-workflow 等）。

### Stage B — YAML 去 vendor

- 运行时新增依赖 `ruamel.yaml`；删除 `vendor/yamlx`（约 5.8MB，含 3.1MB cp36 二进制）。
- 实施前先做上游兼容 spike：vendored 0.18.3 ↔ 上游 0.18.17 / 0.19.1 API 对拍，据结果定版本范围（0.19 起 clib 依赖改名为 clibz）。
- PyYAML 移入 dev 依赖组，仅作对拍 / golden 用途；YAML 1.2 语义合约不变（golden corpus 守护）。

### Stage C — vendor/ 目录退役

- `litejinja2` → `dsl/yaml_dsl/_internal/litejinja2/`（保留名称：它是 Jinja2 兼容子集，名字即语义锚点；唯一运行时消费方在 yaml_dsl config_parsing）。
- `importlibx` → `_internal/utils/importlibx.py`（跨切面共享，沿用 `loggingx` 等 x 后缀惯例）。
- 清理 ruff / coverage / basedpyright 中全部 vendor 例外配置，`vendor/` 目录整体消失。

### 发布 0.20.0

- 全量 `just qa` + `just examples` + bench 冒烟。
- `just bump-versions 0.20.0 YES`；release notes 汇总全部 Breaking：Python floor、YAML 依赖化、vendor/ 与 `vendors/libs` 同步机制移除。
- tag `v0.20.0` → publish（流程不变）。

## 1.0.0 — 冻结发布

- 支持策略与 API 稳定性承诺写入 README / docs；pre-release checklist、benchmark 边界措辞同步更新。
- `just bump-versions 1.0.0` → tag → publish（流程不变）。

## Open / Deferred

- 依赖优选与 extras 扩展（polars / jsonschema 提升等）：**延后**，需更广泛回归测试后再启动。
- ruamel.yaml 0.19.x 兼容 spike 结论（决定 Stage B 版本范围上界）。
- Floor ratchet：3.10 于 2026-10 EOL，属知情保留（企业存量采用面）；floor≥3.11 时删 `_internal/strenum.py`，floor≥3.12 时 `Self`/`override` 改用 stdlib 并删除 `typing-extensions` 依赖。
