# Workspace / Position 索引（pygls 2.x）

## Docs（2.1.1 快照，仅索引）

- `references/pygls-2.1.1/docs/source/servers/howto/work-with-text-documents.rst`

## 用户环境源码入口（在 `$PYGLS_SRC` 下）

- `workspace/workspace.py`：`Workspace`
- `workspace/text_document.py`：`TextDocument`
- `workspace/position_codec.py`：`PositionCodec`
- `capabilities.py`：`ServerCapabilitiesBuilder.choose_position_encoding`（位置编码选择）
- `protocol/language_server.py`：`LanguageServerProtocol.lsp_initialize`（workspace 初始化位置）

## `rg` 模板（在用户环境源码上跑）

- `rg -n "class Workspace\\b|def get_text_document\\b" "$PYGLS_SRC/workspace/workspace.py"`
- `rg -n "class TextDocument\\b|def apply_change\\b" "$PYGLS_SRC/workspace/text_document.py"`
- `rg -n "class PositionCodec\\b|position_(from|to)_client_units|range_(from|to)_client_units" "$PYGLS_SRC/workspace/position_codec.py"`
- `rg -n "choose_position_encoding" "$PYGLS_SRC/capabilities.py"`
- `rg -n "lsp_initialize\\b|Workspace\\(" "$PYGLS_SRC/protocol/language_server.py"`
