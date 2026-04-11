# yaml-dsl-file-resources (delta) Specification

## ADDED Requirements

### Requirement: temp-path creation for atomic file writes MUST mitigate TOCTOU in untrusted output directories

当系统需要为文件输出执行 “temp+replace” 原子写入时（例如 CSV/Excel 文件落盘），系统 MUST 降低在不可信输出目录中的 TOCTOU（time-of-check to time-of-use）可利用性：

- 系统 MUST 将临时文件放置在目标输出目录下的“私有临时目录”中（同文件系统/同父目录层级，保证后续 replace 原子性）
- 私有临时目录 MUST 尽可能收紧权限，使其他用户/进程无法进入该目录替换临时文件条目（例如仅当前用户可访问）
- 系统 MUST 允许第三方库按 path 写入临时文件（不强制要求 fd 写入），并在写入完成后以原子方式 replace 到最终输出路径
- 系统 SHOULD 在 replace 后对私有临时目录进行 best-effort 清理，避免长期残留

#### Scenario: temp path resides in a private directory under output_dir
- **GIVEN** 输出路径为 `/out/report.csv`
- **WHEN** 系统为该输出创建临时路径
- **THEN** 临时路径 MUST 位于 `/out/` 下的私有临时目录内（例如 `/out/.scalim-tmp-*/...`）
- **AND** 其他用户/进程 MUST 不应能够进入该私有目录以替换临时文件条目

#### Scenario: replace remains atomic and final path is unchanged
- **GIVEN** 系统采用私有临时目录策略
- **WHEN** 临时文件写入完成并提交到最终输出路径
- **THEN** 系统 MUST 以原子 replace 的方式生成最终文件
- **AND** 最终输出路径与文件名 MUST 保持不变

