# `scalim.vendor`

本目录承载 `scalim` 运行时所需的 vendor/shim 代码.目标是:

- 保持与根 `ROADMAP.md` Python 支持窗口(floor 3.10)的兼容
- 在 vendors/libs 同步场景下尽量自包含
- 对来源/许可证/用途保持可审计

> 0.20.x Stage A 已移除 `dataclassesx`(→ stdlib `dataclasses`)与
> `compact/typing_extensionsx`(→ `typing` + `typing_extensions>=4.4`).

## compact/importlibx

- **用途**: 显式 import seam(`IMPORT_MODULE` 测试替换点)与可选依赖守卫(`require_optional_dependency`).
- **来源/许可证**: 本仓库内实现(随仓库许可证).
- **更新**: 由维护者按需求扩展;Stage C 计划迁至 `_internal/utils/`.

## yamlx

- **用途**: 为 `vendors/libs` 同步场景提供自包含 `YAML` 解析能力.默认运行时后端为 vendored `ruamel.yaml`(YAML 1.2 语义);vendored `PyYAML` 仅保留为源码/审计/迁移对拍用途(不作为主线运行时入口).
- **来源**: PyPI `PyYAML==6.0.1` 与 `ruamel.yaml==0.18.3`(含可选 `CPython 3.6` `C-extension`).
- **许可证**: MIT(见 `src/scalim/vendor/yamlx/LICENSE.PyYAML-6.0.1.txt` 与 `src/scalim/vendor/yamlx/LICENSE.ruamel.yaml-0.18.3.txt`)
- **更新**: 见 `src/scalim/vendor/yamlx/SOURCE.md`

## litejinja2

- **用途**: `Jinja2` 兼容子集,用于 YAML/模板预编译等场景,避免引入完整 `jinja2` 运行时依赖.
- **来源/许可证**: 本仓库内实现(随仓库许可证).
- **更新**: 若未来切换到上游 `jinja2`,应保留可迁移语义并同步更新相关 specs/skills.
