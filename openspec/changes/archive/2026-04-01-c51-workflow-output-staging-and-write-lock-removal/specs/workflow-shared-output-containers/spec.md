## ADDED Requirements

### Requirement: shared outputs MUST commit into staging and publish on success
系统 MUST 将 workflow 共享输出容器（csv/workbook/sheetbook）的落盘语义收敛为 staging → publish:

- commit 阶段 MUST 写入 staging 唯一路径（不得直接写入最终导出路径）
- workflow 成功结束后 MUST 覆盖发布到最终导出路径（原子 replace）
- 默认清理策略 MUST 为:
  - success: 清理 staging exec dir
  - failure: 保留 staging（便于排障）

staging 路径布局约束:

- 对最终路径 `final_path`,staging MUST 为 `<final_dir>/<dir_name>/<workflow_exec_id>/<filename>`
- `dir_name` 由 `workflow.options.output_staging.dir_name` 提供或缺省为 `.scalim-staging`

#### Scenario: publish overwrites final path on success
- **GIVEN** workflow 成功结束且存在 staged output
- **WHEN** 执行 publish
- **THEN** 最终导出路径 MUST 被原子覆盖为 staged output 的内容
