# 2026-09-08 — Python floor 3.10 + YAML 去 vendor + `scalim.vendor` 退役（0.20.0 统一发布）

> 本卡覆盖 0.20.0 的环境/依赖级 Breaking（c52 / c53 / c54）。YAML **authoring 面没有字段变化**；
> 0.18 及更早的字段级迁移见本目录其它卡（0.10.2 `lookup_chunk_size`、0.10.3 `source_id` 等）。

## Breaking

1. **Python 支持窗口收敛为 3.10–3.14**：`requires-python >= 3.10`（原 >= 3.6）。3.6–3.9 不再受支持；CI 矩阵 [3.10 … 3.14] 分层验证。**迁移一步**：CI / 部署环境升到 3.10+。
2. **YAML 后端切换为 PyPI `ruamel.yaml>=0.19.1`**（原 vendored `scalim.vendor.yamlx`，5.8MB 含 3.1MB cp36 二进制，已移除）。安装 scalim 自动携带；**YAML 1.2 load 语义与 rt 字节幂等合约不变**。
   - 下游若曾直接 `import scalim.vendor.yamlx` → 改 `import ruamel.yaml`（`YAML(typ="rt")` 或 safe load；ruamel 0.19 起 clib 依赖名为 clibz）。
3. **`scalim.vendor.*` 命名空间整体消失**（`vendor/` 目录退役）：
   - `scalim.vendor.dataclassesx` → stdlib `dataclasses`
   - `scalim.vendor.compact`（`StrEnum`/`Self`/`override`/`Literal` 等）→ `_internal/strenum.py`（内部；下游自备 3.11+ `StrEnum` 或自行 backport）、`typing_extensions`（`Self`/`override`，运行时依赖下界 `>=4.4`）、stdlib `typing`
   - `scalim.vendor.litejinja2` / `scalim.vendor.compact.importlibx` → `scalim.dsl.yaml_dsl._internal.litejinja2` / `scalim._internal.utils.importlibx`（**内部**实现路径，不在 public API；下游不得依赖）
   - **迁移一步**：如引用了以上任何 `scalim.vendor.*` 符号，改为对应标准库 / `typing_extensions`；其它情况无需改动。
4. **vendors/libs 下游同步链路移除**：`just sync-project-vendors` 与 `scripts/vendor-sync.py` 已删，不再维护「源码镜像到下游 `vendors/libs/scalim/`」的采用方式。0.10.x 冻结线可 fork 保留该用法。
5. **运行时依赖变化**：新增 `ruamel.yaml>=0.19.1`（下界-only，无上界）；`typing-extensions` 下界提升 `>=4.4`（floor≥3.12 后可整体删除，见根 `ROADMAP.md` ratchet）。

## 非 Breaking（同版落地，供知悉）

- 开发依赖清理：删 7 个零引用 dev 依赖（pyzmq / sqlalchemy / pymysql / python-dotenv / com2ann / types-dataclasses / memory-profiler）；numpy>=1.26、pandas>=2.1、jsonschema>=4.18、zensical>=0.0.51 floors 对齐实测窗口。
- `dump_effective_demand_yaml`（review/debug 用途）排版可能随 ruamel 版本变化：load 语义与 rt 字节幂等合约不变。
- 错误消息文案微调（`.format()` → f-string）：语义不变。
- Marimo 示例改 cells-native 形态（oracle 契约不变）：`notebooks/marimo/` 章节导入方式变化，见 `notebooks/marimo/README*` 与治理检查。

## 指针

- 版本亮点总览：`docs/doc/releases/0.20.0/index.md`
- Python 支持策略与 ratchet：根 `ROADMAP.md`
- Spec：`llmanspec/specs/yaml-backend-migration`（r102/r466/r551）、`llmanspec/specs/governance-module-organization`（r183/r201）
- 归档提案：`llmanspec/changes/archive/2026-09-07-c52-modernize-py310-baseline/`、`.../2026-09-08-c53-yaml-dependency-unvendor/`、`.../2026-09-08-c54-vendor-directory-retirement/`