import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import unquote, urlparse


def test_lsp_code_action_create_minimal_scalim_yaml(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "src").mkdir()

    yaml_path = workspace / "demo.yaml"
    yaml_text = "loader: mymod:myfunc\n"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc, workspace)
    try:
        client.initialize(workspace)

        client.did_open(uri=yaml_path.as_uri(), text=yaml_text)
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        actions = client.code_actions(uri=yaml_path.as_uri(), line=0, character=0)
        create_action = _find_code_action(actions, command="scalim.yaml.createMinimal")
        assert create_action is not None

        client.execute_command(create_action["command"]["command"], create_action["command"].get("arguments") or [])
        assert (workspace / "scalim.yaml").exists()
        content = (workspace / "scalim.yaml").read_text(encoding="utf-8")
        assert "yaml_dsl:" in content
        assert "import_roots" in content
        assert "alias" in content
    finally:
        client.shutdown()


def test_lsp_code_action_add_import_roots_minimal(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "demo").mkdir()
    (workspace / "fragments").mkdir()

    (workspace / "fragments" / "frag.yaml").write_text("x: 1\n", encoding="utf-8")
    (workspace / "demo" / "main.yaml").write_text(
        "\n".join(
            [
                "imports:",
                '  frag: "../fragments/frag.yaml"',
                "name: demo",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "scalim.yaml").write_text(
        "\n".join(
            [
                "yaml_dsl:",
                "  import_roots:",
                "    - path: demo",
                "",
            ]
        ),
        encoding="utf-8",
    )

    yaml_path = workspace / "demo" / "main.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc, workspace)
    try:
        client.initialize(workspace)
        client.did_open(uri=yaml_path.as_uri(), text=yaml_text)
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        actions = client.code_actions(uri=yaml_path.as_uri(), line=0, character=0)
        fix_action = _find_code_action(actions, command="scalim.yaml.addImportRoots", arg_contains="minimal")
        assert fix_action is not None

        client.execute_command(fix_action["command"]["command"], fix_action["command"].get("arguments") or [])
        content = (workspace / "scalim.yaml").read_text(encoding="utf-8")
        assert "fragments" in content
    finally:
        client.shutdown()


def test_lsp_code_action_add_import_root_alias_for_missing_alias(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "fragments").mkdir()
    (workspace / "fragments" / "frag.yaml").write_text("x: 1\n", encoding="utf-8")

    (workspace / "scalim.yaml").write_text(
        "\n".join(
            [
                "yaml_dsl:",
                "  import_roots:",
                "    - path: .",
                "",
            ]
        ),
        encoding="utf-8",
    )

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "imports:",
            '  frag: "@/fragments/frag.yaml"',
            "name: demo",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc, workspace)
    try:
        client.initialize(workspace)
        client.did_open(uri=yaml_path.as_uri(), text=yaml_text)
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        actions = client.code_actions(uri=yaml_path.as_uri(), line=0, character=0)
        fix_action = _find_code_action(actions, command="scalim.yaml.addImportRootAlias")
        assert fix_action is not None

        client.execute_command(fix_action["command"]["command"], fix_action["command"].get("arguments") or [])
        content = (workspace / "scalim.yaml").read_text(encoding="utf-8")
        assert "alias" in content
        assert "@" in content
    finally:
        client.shutdown()


def test_lsp_execute_command_dump_discovery_returns_json_payload(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    yaml_path = workspace / "demo.yaml"
    yaml_text = "loader: demo\n"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc, workspace)
    try:
        client.initialize(workspace)
        payload = client.execute_command("scalim.dumpDiscovery", [yaml_path.as_uri()])
        assert isinstance(payload, dict)
        assert "project_root" in payload
        assert "python_roots" in payload
        assert "allowed_yaml_roots" in payload
    finally:
        client.shutdown()


def test_lsp_execute_command_dump_discovery_missing_args_is_diagnosable(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc, workspace)
    try:
        client.initialize(workspace)
        payload = client.execute_command("scalim.dumpDiscovery", [])
        assert isinstance(payload, dict)
        assert payload.get("error")
        assert "project_root" in payload
        assert "python_roots" in payload
        assert "allowed_yaml_roots" in payload
        assert "scalim_yaml_path" in payload
    finally:
        client.shutdown()


def _start_lsp_server_process(workspace: Path) -> subprocess.Popen[bytes]:
    code = "from scalim_yaml_dsl_lsp.cli import main; raise SystemExit(main(['serve', '--log-level', 'ERROR']))"
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    return subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", code],
        cwd=str(workspace),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )


def _encode_lsp_message(payload: Dict[str, Any]) -> bytes:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    header = "Content-Length: {}\r\n\r\n".format(len(body)).encode("ascii")
    return header + body


def _read_lsp_message(stream) -> Optional[Dict[str, Any]]:
    headers: Dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, _, value = line.decode("ascii", errors="replace").partition(":")
        headers[key.strip().lower()] = value.strip()

    content_length_raw = headers.get("content-length", "")
    if not content_length_raw.isdigit():
        return None
    length = int(content_length_raw)
    body = b""
    while len(body) < length:
        chunk = stream.read(length - len(body))
        if not chunk:
            return None
        body += chunk
    return json.loads(body.decode("utf-8"))


def _uri_to_path(uri: str) -> Optional[Path]:
    parsed = urlparse(str(uri or ""))
    if parsed.scheme != "file":
        return None
    raw_path = unquote(parsed.path or "")
    if not raw_path:
        return None
    return Path(raw_path).expanduser().resolve(strict=False)


def _position_to_offset(text: str, line: int, character: int) -> int:
    if line <= 0 and character <= 0:
        return 0
    lines = text.splitlines(keepends=True)
    if not lines:
        return 0
    if line >= len(lines):
        return len(text)
    return sum(len(lines[i]) for i in range(line)) + int(character)


def _apply_text_edits(text: str, edits: List[Dict[str, Any]]) -> str:
    parsed: List[tuple[int, int, str]] = []
    for edit in edits:
        rng = edit.get("range") or {}
        start = rng.get("start") or {}
        end = rng.get("end") or {}
        start_off = _position_to_offset(text, int(start.get("line", 0)), int(start.get("character", 0)))
        end_off = _position_to_offset(text, int(end.get("line", 0)), int(end.get("character", 0)))
        parsed.append((start_off, end_off, str(edit.get("newText", ""))))
    parsed.sort(key=lambda item: item[0], reverse=True)
    out = str(text)
    for start_off, end_off, new_text in parsed:
        out = out[:start_off] + new_text + out[end_off:]
    return out


def _apply_workspace_edit(workspace: Path, edit: Dict[str, Any]) -> tuple[bool, str]:
    # We apply edits to disk files for tests. This is a minimal implementation
    # that supports the operations we emit in the server.
    changes = edit.get("changes")
    if isinstance(changes, dict):
        for uri, edits in changes.items():
            path = _uri_to_path(str(uri))
            if path is None:
                return False, "unsupported uri in changes"
            old = path.read_text(encoding="utf-8") if path.exists() else ""
            new = _apply_text_edits(old, list(edits or []))
            path.write_text(new, encoding="utf-8")

    doc_changes = edit.get("documentChanges")
    if isinstance(doc_changes, list):
        for item in doc_changes:
            if isinstance(item, dict) and item.get("kind") == "create":
                path = _uri_to_path(str(item.get("uri") or ""))
                if path is None:
                    return False, "unsupported create uri"
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    path.write_text("", encoding="utf-8")
                continue

            if not isinstance(item, dict) or "textDocument" not in item:
                return False, "unsupported document change"
            doc = item.get("textDocument") or {}
            uri = str(doc.get("uri") or "")
            path = _uri_to_path(uri)
            if path is None:
                return False, "unsupported textDocument uri"
            old = path.read_text(encoding="utf-8") if path.exists() else ""
            new = _apply_text_edits(old, list(item.get("edits") or []))
            path.write_text(new, encoding="utf-8")

    return True, ""


def _find_code_action(
    actions: List[Dict[str, Any]],
    *,
    command: str,
    arg_contains: str = "",
) -> Optional[Dict[str, Any]]:
    for action in actions:
        cmd = action.get("command") or {}
        if cmd.get("command") != command:
            continue
        if not arg_contains:
            return action
        args = cmd.get("arguments") or []
        if any(arg_contains in str(a) for a in args):
            return action
    return None


class _LspClient:
    def __init__(self, proc: subprocess.Popen[bytes], workspace: Path) -> None:
        if proc.stdin is None or proc.stdout is None or proc.stderr is None:
            raise RuntimeError("unexpected: subprocess pipes not available")
        self._proc = proc
        self._workspace = workspace
        self._stdin = proc.stdin
        self._stdout = proc.stdout
        self._stderr = proc.stderr
        self._inbox: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._stash: List[Dict[str, Any]] = []
        self._next_id = 1
        self._stderr_lines: List[str] = []

        self._stdout_thread = threading.Thread(target=self._stdout_loop, daemon=True)
        self._stderr_thread = threading.Thread(target=self._stderr_loop, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def initialize(self, workspace: Path) -> None:
        init_id = self._send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = self.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp
        self._send_notification("initialized", {})

    def did_open(self, *, uri: str, text: str) -> None:
        self._send_notification(
            "textDocument/didOpen",
            {"textDocument": {"uri": uri, "languageId": "yaml", "version": 1, "text": str(text)}},
        )

    def code_actions(self, *, uri: str, line: int, character: int) -> List[Dict[str, Any]]:
        req_id = self._send_request(
            "textDocument/codeAction",
            {
                "textDocument": {"uri": uri},
                "range": {
                    "start": {"line": int(line), "character": int(character)},
                    "end": {"line": int(line), "character": int(character)},
                },
                "context": {"diagnostics": []},
            },
        )
        resp = self.recv_until(lambda msg: msg.get("id") == req_id, timeout=10.0)
        assert "error" not in resp
        result = resp.get("result") or []
        assert isinstance(result, list)
        return result

    def execute_command(self, command: str, arguments: List[Any]) -> Any:
        req_id = self._send_request(
            "workspace/executeCommand",
            {"command": str(command), "arguments": list(arguments)},
        )
        resp = self.recv_until(lambda msg: msg.get("id") == req_id, timeout=10.0)
        assert "error" not in resp
        return resp.get("result")

    def recv_until(self, predicate: Callable[[Dict[str, Any]], bool], *, timeout: float) -> Dict[str, Any]:
        end = time.monotonic() + float(timeout)
        for idx, item in enumerate(list(self._stash)):
            if predicate(item):
                return self._stash.pop(idx)

        while time.monotonic() < end:
            remaining = end - time.monotonic()
            try:
                msg = self._inbox.get(timeout=max(remaining, 0.01))
            except queue.Empty:
                continue
            if predicate(msg):
                return msg
            self._stash.append(msg)

        raise AssertionError("timeout waiting for LSP message; stderr:\n{}".format("".join(self._stderr_lines[-50:])))

    def shutdown(self) -> None:
        if self._proc.poll() is not None:
            return
        try:
            shutdown_id = self._send_request("shutdown", None)
            _ = self.recv_until(lambda msg: msg.get("id") == shutdown_id, timeout=5.0)
            self._send_notification("exit", None)
            self._stdin.close()
            self._proc.wait(timeout=5.0)
        except Exception:  # noqa: BLE001
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def _send_request(self, method: str, params: Optional[Dict[str, Any]]) -> int:
        msg_id = int(self._next_id)
        self._next_id += 1
        msg: Dict[str, Any] = {"jsonrpc": "2.0", "id": msg_id, "method": str(method)}
        if params is not None:
            msg["params"] = params
        self._send(msg)
        return msg_id

    def _send_notification(self, method: str, params: Optional[Dict[str, Any]]) -> None:
        msg: Dict[str, Any] = {"jsonrpc": "2.0", "method": str(method)}
        if params is not None:
            msg["params"] = params
        self._send(msg)

    def _send(self, msg: Dict[str, Any]) -> None:
        payload = _encode_lsp_message(msg)
        self._stdin.write(payload)
        self._stdin.flush()

    def _stdout_loop(self) -> None:
        while True:
            msg = _read_lsp_message(self._stdout)
            if msg is None:
                return
            if "id" in msg and "method" in msg:
                self._handle_server_request(msg)
                continue
            self._inbox.put(msg)

    def _handle_server_request(self, msg: Dict[str, Any]) -> None:
        req_id = msg.get("id")
        method = msg.get("method")
        if method == "workspace/applyEdit":
            params = msg.get("params") or {}
            edit = params.get("edit") or {}
            applied, reason = _apply_workspace_edit(self._workspace, edit)
            result = {"applied": bool(applied)}
            if reason:
                result["failureReason"] = str(reason)
            self._send({"jsonrpc": "2.0", "id": req_id, "result": result})
            return

        self._send(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": "method not supported"},
            }
        )

    def _stderr_loop(self) -> None:
        while True:
            line = self._stderr.readline()
            if not line:
                return
            self._stderr_lines.append(line.decode("utf-8", errors="replace"))
