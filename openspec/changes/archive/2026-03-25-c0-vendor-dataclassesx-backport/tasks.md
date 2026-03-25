## 1. vendoring: dataclassesx + provenance

- [x] 1.1 新增 `src/scalim/vendor/dataclassesx/` 包,引入 `dataclasses` backport 的 vendored 源码(仅运行时所需部分)并提供最小可用入口。
- [x] 1.2 在 `src/scalim/vendor/dataclassesx/` 增加 `SOURCE.md`(或等价文件)记录来源(上游版本/commit)与许可证信息,并说明本地改动点(若有)。
- [x] 1.3 更新 `src/scalim/vendor/README.md` 增加 `dataclassesx` 条目(来源/许可证 + usage + 更新策略)。

## 2. runtime facade: `scalim.vendor.dataclassesx`

- [x] 2.1 实现 `src/scalim/vendor/dataclassesx/__init__.py` facade:
  - Python >= 3.7 优先使用 stdlib `dataclasses`
  - Python 3.6 使用 vendored backport 实现
- [x] 2.2 确保 facade 至少导出 `dataclass`/`field`/`replace`/`asdict`(以及 `scalim` 现有使用到的其它符号)且 import 无副作用/无循环依赖。

## 3. 迁移: `src/scalim/` 内部 dataclasses 使用面

- [x] 3.1 将 `src/scalim/**` 内所有 `from dataclasses import ...`/`import dataclasses` 替换为对 `vendor/dataclassesx` 的相对导入(示例: `from ..vendor.dataclassesx import dataclass`)。
- [x] 3.2 确认 `src/scalim/**` 内不再出现 `from scalim...`/`import scalim` 形式的包内绝对导入(避免 vendors 化/多份包共存时混入错误实现)。
- [x] 3.3 运行 `just stdlib-collisions-check` 确认 `src/scalim/*` 模块名不与标准库冲突;新增模块名同时避免与常见三方库同名。

## 4. 依赖与锁文件

- [x] 4.1 从 `pyproject.toml` 的 `[project].dependencies` 移除 `dataclasses;python_version<'3.7'` 运行时依赖。
- [x] 4.2 更新 `uv.lock`(如需要)以反映依赖变更,并确保 `just uv-lock-check`/`just quick-check-only-py` 通过。

## 5. Python 3.6 验证与门禁

- [x] 5.1 更新 `scripts/check-py36-typingext-docker.sh`：在 Python 3.6 分支不再安装 `dataclasses`,以验证 `scalim` 在 py36 下对外部 backport 零依赖。
- [x] 5.2 运行 `just py36-typingext-check` 确认 Python 3.6 import smoke 通过。
- [x] 5.3 运行 `just quick-check-only-py` 与 `just openspec-check` 作为基础验收门禁。
