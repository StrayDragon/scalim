# Protocol 扩展 / 自定义 JSON-RPC 索引（pygls 2.x）

## Docs（2.1.1 快照，仅索引）

- `references/pygls-2.1.1/docs/source/pygls/howto/send-custom-messages.rst`
- `references/pygls-2.1.1/docs/source/pygls/howto/use-custom-converter.rst`（自定义类型结构化也常与协议扩展一起用）

## 用户环境源码入口（在 `$PYGLS_SRC` 下）

- `protocol/json_rpc.py`：`JsonRPCProtocol`（`notify`、`send_request(_async)`、消息结构化/分发入口）
- `protocol/language_server.py`：`LanguageServerProtocol.get_message_type/get_result_type`（LSP method 映射）
- `protocol/__init__.py`：`default_converter`
- `server.py`：`JsonRPCServer`（自定义 protocol 注入点）

## `rg` 模板（在用户环境源码上跑）

- 自定义消息发送入口：`rg -n "def notify\\b|def send_request\\b|def send_request_async\\b" "$PYGLS_SRC/protocol/json_rpc.py"`
- 类型映射入口：`rg -n "def get_message_type\\b|def get_result_type\\b" "$PYGLS_SRC/protocol/json_rpc.py" "$PYGLS_SRC/protocol/language_server.py"`
- converter：`rg -n "default_converter|register_structure_hook|structure\\(" "$PYGLS_SRC/protocol" "$PYGLS_SRC"`
