# Server 核心索引（pygls 2.x）

## Docs（2.1.1 快照，仅索引）

- `references/pygls-2.1.1/docs/source/servers/howto/run-a-server.rst`
- `references/pygls-2.1.1/docs/source/servers/howto/access-server-instance.rst`
- `references/pygls-2.1.1/docs/source/servers/howto/customise-error-reporting.rst`
- `references/pygls-2.1.1/docs/source/servers/howto/give-user-feedback.rst`
- `references/pygls-2.1.1/docs/source/servers/howto/get-client-configuration.rst`
- `references/pygls-2.1.1/docs/source/servers/howto/implement-workspace-commands.rst`
- `references/pygls-2.1.1/docs/source/servers/howto/add-notebook-support.rst`

## 用户环境源码入口（在 `$PYGLS_SRC` 下）

- `lsp/server.py`：`LanguageServer`
- `lsp/_base_server.py`：`BaseLanguageServer`（generated；LSP method wrappers）
- `server.py`：`JsonRPCServer`（`start_io/start_tcp/start_ws`、decorators）
- `feature_manager.py`：`FeatureManager`（feature/command/thread 注册、server 注入）
- `protocol/language_server.py`：`LanguageServerProtocol`（built-in handlers、executeCommand 处理）

## `rg` 模板（在用户环境源码上跑）

- `rg -n "class LanguageServer\\b" "$PYGLS_SRC/lsp/server.py"`
- `rg -n "class BaseLanguageServer\\b" "$PYGLS_SRC/lsp/_base_server.py"`
- `rg -n "class JsonRPCServer\\b|def start_(io|tcp|ws)\\b" "$PYGLS_SRC/server.py"`
- `rg -n "class FeatureManager\\b|def (feature|command|thread)\\b" "$PYGLS_SRC/feature_manager.py"`
- `rg -n "lsp_workspace__execute_command|_prepare_command_arguments|_get_handler_params_annotations" "$PYGLS_SRC/protocol/language_server.py"`
