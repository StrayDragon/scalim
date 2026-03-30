# `scalim.vendor`

本目录承载 `scalim` 运行时所需的 vendor/shim 代码.目标是:

- 保持 Python 3.6 运行时可用性
- 在 vendors/libs 同步场景下尽量自包含
- 对来源/许可证/用途保持可审计

## dataclassesx

- **用途**: 为 Python 3.6 提供自包含的 dataclasses 能力入口 `scalim.vendor.dataclassesx`.
- **来源**: PyPI `dataclasses==0.8`(https://github.com/ericvsmith/dataclasses)
- **许可证**: Apache-2.0(见 `src/scalim/vendor/dataclassesx/LICENSE.txt`)
- **更新**: 见 `src/scalim/vendor/dataclassesx/SOURCE.md`

## compact/typing_extensionsx.py

- **用途**: Python 3.6 + 旧 `typing_extensions` 兼容层; `src/scalim/` 内扩展 typing 能力的唯一入口.
- **来源/许可证**: 本仓库内实现(随仓库许可证).
- **更新**: 由维护者按需求扩展,并保持对旧 `typing_extensions` 的运行时兼容.

## yamlx

- **用途**: 为 `vendors/libs` 同步场景提供自包含 `YAML` 解析能力.默认运行时入口为 `scalim.vendor.yamlx.yaml`(PyYAML);同时 vendors `ruamel.yaml` 供实验/升级工具使用.
- **来源**: PyPI `PyYAML==6.0.1` 与 `ruamel.yaml==0.18.3`（含可选 `CPython 3.6` `C-extension`）。
- **许可证**: MIT(见 `src/scalim/vendor/yamlx/LICENSE.PyYAML-6.0.1.txt` 与 `src/scalim/vendor/yamlx/LICENSE.ruamel.yaml-0.18.3.txt`)
- **更新**: 见 `src/scalim/vendor/yamlx/SOURCE.md`

## litejinja2

- **用途**: `Jinja2` 兼容子集,用于 YAML/模板预编译等场景,避免引入完整 `jinja2` 运行时依赖.
- **来源/许可证**: 本仓库内实现(随仓库许可证).
- **更新**: 若未来切换到上游 `jinja2`,应保留可迁移语义并同步更新相关 specs/skills.

## literich

- **用途**: 轻量的表格/面板渲染工具,用于 CLI/调试输出,避免引入完整 `rich` 运行时依赖.
- **来源/许可证**: 本仓库内实现(随仓库许可证).
- **更新**: 保持依赖最小化;若引入上游依赖,需更新运行时依赖边界与门禁.
