# language: zh-CN
# capability: vendor-dataclassesx
# purpose: 为 `scalim/` 提供一个可 vendors 化、可审计的 dataclasses 能力入口,在保持 Python 3.6 运行时兼容的同时避免依赖外部 `dataclasses` backport,并避免包内绝对导入在多份包共存时混入错误实现。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: vendor-dataclassesx

  @req:r84 @human
  场景: 提供 `scalim.vendor.dataclassesx` 入口
    - 系统 MUST 提供 `scalim.vendor.dataclassesx` 作为 dataclasses 能力的唯一入口,并覆盖 `scalim` 运行时使用到的核心符号(至少包括 `dataclass`、`field`、`replace`、`asdict`)。

  @req:r328 @human
  场景: Python 3.6 环境不依赖外部 `dataclasses` backport
    - 系统 MUST 在 Python 3.6 环境下使 `scalim.vendor.dataclassesx` 可用,且不得依赖外部安装的 `dataclasses` backport 包。

  @req:r450 @human
  场景: scalim 内部遵循 dataclassesx 导入规范
    - 系统 MUST 确保 `scalim/` 内部模块遵循导入规范：(1) 不得直接导入 `dataclasses`；(2) 必须使用相对导入引用 `dataclassesx`，避免绝对导入以防 vendors 化/多份包共存时引入错误实现。

  @req:r537 @human
  场景: 发行物不再声明 `dataclasses` 运行时依赖
    - 系统 MUST 在项目配置中移除 `dataclasses` 运行时依赖项,以避免将 backport 作为运行时外部依赖暴露给调用方。

  @req:r611 @human
  场景: vendored provenance 可审计
    - 系统 MUST 记录 vendored `dataclassesx` 的来源与许可证信息,并在 vendor README 中维护其用途与更新策略入口。
  @req:r84 @human
  场景: 运行时可导入核心符号
    - 必须成立：当 调用方执行 `from scalim.vendor.dataclassesx import dataclass, field, replace, asdict`；那么 导入 MUST 成功
    当 调用方执行 `from scalim.vendor.dataclassesx import dataclass, field, replace, asdict`
    那么 导入 MUST 成功
  @req:r328 @human
  场景: 干净-python-3-6-环境-import-smoke
    - 必须成立：当 在干净的 Python 3.6 环境中导入 dataclassesx；那么 导入 MUST 成功
    当 在干净的 Python 3.6 环境中导入 dataclassesx
    那么 导入 MUST 成功
  @req:r450 @human
  场景: 无-dataclasses-直接导入
    - 必须成立：当 扫描 `scalim/` 下的 import 语句；那么 不应出现 `from dataclasses import` 或 `import dataclasses`
    当 扫描 `scalim/` 下的 import 语句
    那么 不应出现 `from dataclasses import` 或 `import dataclasses`

  @req:r450 @human
  场景: 使用相对导入引用-dataclassesx
    - 必须成立：当 扫描 `scalim/` 下的 import 语句；那么 不应出现 `from scalim.vendor.dataclassesx` 的绝对导入形式
    当 扫描 `scalim/` 下的 import 语句
    那么 不应出现 `from scalim.vendor.dataclassesx` 的绝对导入形式
  @req:r537 @human
  场景: 项目配置不含-dataclasses-依赖
    - 必须成立：当 审阅项目配置的依赖项；那么 不应存在 `dataclasses` 依赖条目
    当 审阅项目配置的依赖项
    那么 不应存在 `dataclasses` 依赖条目
  @req:r611 @human
  场景: vendor-readme-记录-dataclassesx
    - 必须成立：当 审阅 vendor README；那么 MUST 存在 `dataclassesx` 的来源/许可证与 usage 说明
    当 审阅 vendor README
    那么 MUST 存在 `dataclassesx` 的来源/许可证与 usage 说明
