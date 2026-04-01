# Built-in features / Lifecycle 索引（pygls 2.x）

## Docs（2.1.1 快照，仅索引）

- `references/pygls-2.1.1/docs/source/servers/reference/built-in-features.rst`

## 用户环境源码入口（在 `$PYGLS_SRC` 下）

- `protocol/language_server.py`：`LanguageServerProtocol`（built-in LSP handlers）
- `protocol/json_rpc.py`：`JsonRPCProtocol`（分发/错误/取消相关逻辑）
- `server.py`：`JsonRPCServer.shutdown`（进程/连接结束路径）

## `rg` 模板（在用户环境源码上跑）

- 列出所有 built-in LSP handlers：`rg -n "@lsp_method\\(" "$PYGLS_SRC/protocol/language_server.py"`
- 初始化/退出相关定位：`rg -n "lsp_(initialize|shutdown|exit)\\b" "$PYGLS_SRC/protocol/language_server.py"`
- 文档同步相关定位：`rg -n "TEXT_DOCUMENT_DID_(OPEN|CHANGE|CLOSE)" "$PYGLS_SRC/protocol/language_server.py"`
- notebook 同步相关定位：`rg -n "NOTEBOOK_DOCUMENT_DID_(OPEN|CHANGE|CLOSE)" "$PYGLS_SRC/protocol/language_server.py"`
- workspace folder 相关定位：`rg -n "WORKSPACE_DID_CHANGE_WORKSPACE_FOLDERS" "$PYGLS_SRC/protocol/language_server.py"`
- 取消相关定位：`rg -n "CANCEL_REQUEST|\\$\\/cancelRequest|cancel\\(" "$PYGLS_SRC/protocol" "$PYGLS_SRC/server.py"`
