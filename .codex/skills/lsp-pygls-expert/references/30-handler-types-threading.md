# Handler / Threading / Cancellation 索引（pygls 2.x）

## Docs（2.1.1 快照，仅索引）

- `references/pygls-2.1.1/docs/source/pygls/reference/message-handler-types.rst`

## 用户环境源码入口（在 `$PYGLS_SRC` 下）

- `protocol/json_rpc.py`：`JsonRPCProtocol._execute_handler` / `_run_generator`（handler 调度）
- `feature_manager.py`：`FeatureManager.thread` / `is_thread_function`（thread 标记）
- `server.py`：`JsonRPCServer.thread_pool`（线程池来源）
- `protocol/language_server.py`：`LanguageServerProtocol.lsp_shutdown`（shutdown 取消路径）

## `rg` 模板（在用户环境源码上跑）

- handler 调度主入口：`rg -n "def _execute_handler\\b" "$PYGLS_SRC/protocol/json_rpc.py"`
- generator 路径：`rg -n "inspect\\.isgeneratorfunction|def _run_generator\\b" "$PYGLS_SRC/protocol/json_rpc.py"`
- thread 标记：`rg -n "def thread\\b|ATTR_EXECUTE_IN_THREAD|is_thread_function" "$PYGLS_SRC/feature_manager.py" "$PYGLS_SRC/protocol/json_rpc.py"`
- 线程池：`rg -n "def thread_pool\\b|ThreadPoolExecutor" "$PYGLS_SRC/server.py"`
- 取消/关闭：`rg -n "CANCEL_REQUEST|\\$\\/cancelRequest|cancel\\(|lsp_shutdown\\b" "$PYGLS_SRC/protocol" "$PYGLS_SRC/server.py"`
