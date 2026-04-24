# 迁移索引：v1 → v2（pygls）

## Docs（2.1.1 快照，仅索引）

- `references/pygls-2.1.1/docs/source/pygls/howto/migrate-to-v1.rst`
- `references/pygls-2.1.1/docs/source/pygls/howto/migrate-to-v2.rst`

## 用户环境源码入口（在 `$PYGLS_SRC` 下）

- `lsp/_base_server.py`（generated；用于核对“server 侧可调用的方法名/签名”）
- `protocol/language_server.py`（`workspace/executeCommand` 相关逻辑）
- `protocol/json_rpc.py`（自定义 notify/request 等低层 API）
- `workspace/*`（Workspace/TextDocument/PositionCodec 的命名与行为）

## `rg` 模板（在**你的项目代码**里跑，找需要升级的旧写法）

- 旧 import：`rg -n "from pygls\\.server import LanguageServer" .`
- 自定义通知旧 API：`rg -n "send_notification\\(" .`
- Workspace/TextDocument 旧命名：`rg -n "Workspace\\.documents\\b|get_document\\b|put_document\\b|remove_document\\b|update_document\\b|\\bDocument\\b" .`
- 旧的 server 方法名（按迁移文档对照）：`rg -n "\\.apply_edit\\b|\\.publish_diagnostics\\b|\\.show_message\\b|\\.register_capability\\b|\\.unregister_capability\\b" .`
