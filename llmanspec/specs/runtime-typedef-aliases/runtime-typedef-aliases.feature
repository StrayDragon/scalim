# language: zh-CN
# capability: runtime-typedef-aliases
# purpose: 收敛公开记录键类型别名：BusinessKey 为 SSOT，移除 RowId/RowIdSeq/RowIdList 兼容别名。
# scope: src/, tests/

功能: runtime-typedef-aliases

  @req:r224 @human
  场景: public RowId aliases MUST be removed in favor of BusinessKey
    - 系统 MUST 将记录业务键的公开类型 SSOT 收敛为 BusinessKey（及 RecordKey 体系）。公开兼容别名 RowId / RowIdSeq / RowIdList MUST 被移除；LoaderResult 等公开或半公开类型注解 MUST 使用 BusinessKey 而非 RowId。迁移提示 MUST 出现在变更说明或 upgrade 笔记中。

  @req:r224 @human
  场景: rowid-aliases-are-not-importable
    - 必须成立：当 调用方尝试 from scalim.typedefs import RowId 或等价公开导出；那么 导入 MUST 失败或该名字 MUST 不再作为公开别名存在；推荐导入 BusinessKey
    当 调用方尝试 from scalim.typedefs import RowId 或等价公开导出
    那么 导入 MUST 失败或该名字 MUST 不再作为公开别名存在；推荐导入 BusinessKey
