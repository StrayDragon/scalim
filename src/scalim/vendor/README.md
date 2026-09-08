# `scalim.vendor`

本目录承载 `scalim` 运行时所需的 vendor/shim 代码.目标是:

- 保持与根 `ROADMAP.md` Python 支持窗口(floor 3.10)的兼容
- 对来源/许可证/用途保持可审计

> 0.20.x Stage A 已移除 `dataclassesx`(→ stdlib `dataclasses`)与
> `compact/typing_extensionsx`(→ `typing` + `typing_extensions>=4.4`).
> Stage B 已移除 `yamlx`(→ 外部依赖 `ruamel.yaml>=0.19.1`).

## compact/importlibx

- **用途**: 显式 import seam(`IMPORT_MODULE` 测试替换点)与可选依赖守卫(`require_optional_dependency`).
- **来源/许可证**: 本仓库内实现(随仓库许可证).
- **更新**: 由维护者按需求扩展;Stage C 计划迁至 `_internal/utils/`.

## litejinja2

- **用途**: `Jinja2` 兼容子集,用于 YAML/模板预编译等场景,避免引入完整 `jinja2` 运行时依赖.
- **来源/许可证**: 本仓库内实现(随仓库许可证).
- **更新**: 若未来切换到上游 `jinja2`,应保留可迁移语义并同步更新相关 specs/skills.
