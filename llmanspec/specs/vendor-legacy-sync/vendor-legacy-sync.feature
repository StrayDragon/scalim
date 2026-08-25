# language: zh-CN
# capability: vendor-legacy-sync
# purpose: 为下游采用 `vendors/libs/` 导入链路的旧工程提供一个可审计、可重复的同步入口,用于将本仓库的 `src/scalim/` vendors 化后镜像到目标 `<vendors/libs>/scalim/`。默认仅预览(dry-run),并在显式确认时执行实际同步。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: vendor-legacy-sync

  @req:r85 @human
  场景: 提供 vendors 同步的 `just` 快捷入口
    - 系统 MUST 在仓库根 `justfile` 中提供一个快捷 recipe,用于触发 vendors 同步脚本;目标路径 MUST 由调用方显式传入,不得写入仓库版本控制。

  @req:r329 @human
  场景: 同步脚本镜像 `src/scalim` 到 `<dest>/scalim`
    - 系统 MUST 提供一个同步脚本,用于将仓库的 `src/scalim/` 镜像同步到下游旧工程的 `vendors/libs/scalim/` 导入链路。 同步脚本 MUST 满足: - 接收目标目录参数 `--dest <vendors/libs>` 并将同步落点固定为 `<dest>/scalim/`。 - 默认 MUST 以 dry-run 方式执行镜像式同步预览（等价于 `rsync -a --delete --dry-run`）。 - 当调用方显式确认执行实际同步时,脚本 MUST 执行镜像式同步（等价于 `rsync -a --delete`）。 - MUST 提供 `--apply` 用于显式触发实际写入。 - MUST 排除非源码产物(至少包含 `__pycache__` 与 `*.pyc`)。 - MUST 提供 `--dry-run` 以预览变更。 - MUST 对明显危险的目标路径做硬拒绝(例如 `--dest /`),避免误删。

  @req:r451 @human
  场景: vendors 同步包含 `README.md`
    - 同步脚本 MUST 将仓库根的 `README.md` 同步到目标目录下的 `scalim/` 子目录。

  @req:r538 @human
  场景: vendors synced scalim MUST be able to parse YAML without external installs
    - 当 `src/scalim/` 通过 `scripts/vendor-sync.py` 被镜像到下游 `vendors/libs/scalim/` 导入链路后,系统 MUST 在 Python 3.6 环境中具备可用的 YAML 解析能力,且 MUST 不依赖下游额外安装 `PyYAML`/`ruamel.yaml`。
  @req:r85 @human
  场景: 默认-dry-run-预览
    - 必须成立：当 开发者执行 `just sync-project-vendors <vendors/libs>`；那么 recipe MUST 触发同步脚本并将目标路径传入脚本（默认 `dry-run` 预览）
    当 开发者执行 `just sync-project-vendors <vendors/libs>`
    那么 recipe MUST 触发同步脚本并将目标路径传入脚本（默认 `dry-run` 预览）

  @req:r85 @human
  场景: 实际同步需要显式确认-token
    - 必须成立：当 开发者执行 `just sync-project-vendors <vendors/libs> YES`；那么 recipe MUST 执行实际同步（非 dry-run）
    当 开发者执行 `just sync-project-vendors <vendors/libs> YES`
    那么 recipe MUST 执行实际同步（非 dry-run）
  @req:r329 @human
  场景: 镜像同步会移除残留文件
    - 必须成立：假如 目标 `<dest>/scalim/` 中存在历史残留文件；当 使用 `--apply` 执行同步脚本；那么 同步结果 MUST 与源 `src/scalim/` 保持一致且残留文件 MUST 被移除
    假如 目标 `<dest>/scalim/` 中存在历史残留文件
    当 使用 `--apply` 执行同步脚本
    那么 同步结果 MUST 与源 `src/scalim/` 保持一致且残留文件 MUST 被移除

  @req:r329 @human
  场景: dry-run-不产生写入
    - 必须成立：当 使用 `--dry-run` 执行同步脚本；那么 脚本 MUST 不写入目标目录且输出计划变更
    当 使用 `--dry-run` 执行同步脚本
    那么 脚本 MUST 不写入目标目录且输出计划变更
  @req:r451 @human
  场景: 目标包含-readme
    - 必须成立：当 执行同步脚本；那么 目标目录中的 `scalim/README.md` MUST 存在
    当 执行同步脚本
    那么 目标目录中的 `scalim/README.md` MUST 存在
  @req:r538 @human
  场景: downstream-vendors-runtime-imports-yaml-dsl-successfully
    - 必须成立：假如 下游工程仅 vendors 化同步了 `src/scalim/` 源码,且运行环境为 Python 3.6；当 下游导入并执行 YAML DSL 的解析入口(例如 `scalim.dsl.yaml_dsl.validation_service` 或 `scalim.dsl.yaml_dsl._internal.config_parsing.yaml_load`)；那么 导入与 YAML 解析 MUST 成功
    假如 下游工程仅 vendors 化同步了 `src/scalim/` 源码,且运行环境为 Python 3.6
    当 下游导入并执行 YAML DSL 的解析入口(例如 `scalim.dsl.yaml_dsl.validation_service` 或 `scalim.dsl.yaml_dsl._internal.config_parsing.yaml_load`)
    那么 导入与 YAML 解析 MUST 成功

  @req:r538 @human
  场景: scalim-yaml-parsing-uses-vendored-ruamel-yaml-without-extern
    - 必须成立：假如 `src/scalim/vendor/yamlx/` 内包含 vendors 化的 YAML 实现；当 `scalim` 在运行时解析 YAML 文本；那么 系统 MUST 使用 vendored `ruamel.yaml` 作为默认 YAML 解析实现
    假如 `src/scalim/vendor/yamlx/` 内包含 vendors 化的 YAML 实现
    当 `scalim` 在运行时解析 YAML 文本
    那么 系统 MUST 使用 vendored `ruamel.yaml` 作为默认 YAML 解析实现
