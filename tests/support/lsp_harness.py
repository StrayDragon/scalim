import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse


DEFAULT_TIMEOUT_S = float(os.environ.get("SCALIM_YAML_DSL_LSP_TIMEOUT_S", "10.0"))
TRACE_KEEP_N = int(os.environ.get("SCALIM_YAML_DSL_LSP_TRACE_KEEP_N", "80"))
DIAGNOSTICS_SETTLE_S = float(os.environ.get("SCALIM_YAML_DSL_LSP_DIAGNOSTICS_SETTLE_S", "0.2"))


def start_yaml_dsl_lsp_server(workspace: Path) -> subprocess.Popen[bytes]:
    code = "from scalim_yaml_dsl_lsp.cli import main; raise SystemExit(main(['serve', '--log-level', 'ERROR']))"
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    env["SCALIM_YAML_DSL_LSP_DID_CHANGE_DEBOUNCE_MS"] = "0"
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
    parsed: List[Tuple[int, int, str]] = []
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


def _apply_workspace_edit(workspace: Path, edit: Dict[str, Any]) -> Tuple[bool, str]:
    # Minimal implementation for `workspace/applyEdit` used by YAML DSL LSP code actions.
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


class LspSession:
    def __init__(self, proc: subprocess.Popen[bytes], *, workspace: Path) -> None:
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
        self._trace: List[str] = []

        self._stdout_thread = threading.Thread(target=self._stdout_loop, daemon=True)
        self._stderr_thread = threading.Thread(target=self._stderr_loop, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def initialize(self, workspace: Optional[Path] = None) -> None:
        workspace = workspace or self._workspace
        init_id = self.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = self.recv_until(lambda msg: msg.get("id") == init_id, timeout=DEFAULT_TIMEOUT_S)
        if "error" in init_resp:
            raise AssertionError("initialize failed: {}".format(init_resp.get("error")))
        self.send_notification("initialized", {})

    def did_open(self, *, uri: str, text: str, version: int = 1, language_id: str = "yaml") -> None:
        self.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": str(uri),
                    "languageId": str(language_id),
                    "version": int(version),
                    "text": str(text),
                }
            },
        )

    def did_change(self, *, uri: str, text: str, version: int) -> None:
        self.send_notification(
            "textDocument/didChange",
            {
                "textDocument": {"uri": str(uri), "version": int(version)},
                "contentChanges": [{"text": str(text)}],
            },
        )

    def wait_for_diagnostics(self, *, uri: str, timeout: float = DEFAULT_TIMEOUT_S) -> Dict[str, Any]:
        expected_uri = str(uri)

        def _is_diag(msg: Dict[str, Any]) -> bool:
            if msg.get("method") != "textDocument/publishDiagnostics":
                return False
            params = msg.get("params") or {}
            return str(params.get("uri") or "") == expected_uri

        last = self.recv_until(_is_diag, timeout=float(timeout))
        settle_deadline = time.monotonic() + float(DIAGNOSTICS_SETTLE_S)
        while time.monotonic() < settle_deadline:
            remaining = settle_deadline - time.monotonic()
            try:
                msg = self._inbox.get(timeout=max(remaining, 0.01))
            except queue.Empty:
                break
            if _is_diag(msg):
                last = msg
                continue
            self._stash.append(msg)
        return last

    def definition(self, *, uri: str, line: int, character: int) -> Any:
        req_id = self.send_request(
            "textDocument/definition",
            {"textDocument": {"uri": str(uri)}, "position": {"line": int(line), "character": int(character)}},
        )
        resp = self.recv_until(lambda msg: msg.get("id") == req_id, timeout=DEFAULT_TIMEOUT_S)
        if "error" in resp:
            raise AssertionError("definition failed: {}".format(resp.get("error")))
        return resp.get("result")

    def hover(self, *, uri: str, line: int, character: int) -> Any:
        req_id = self.send_request(
            "textDocument/hover",
            {"textDocument": {"uri": str(uri)}, "position": {"line": int(line), "character": int(character)}},
        )
        resp = self.recv_until(lambda msg: msg.get("id") == req_id, timeout=DEFAULT_TIMEOUT_S)
        if "error" in resp:
            raise AssertionError("hover failed: {}".format(resp.get("error")))
        return resp.get("result")

    def completion(self, *, uri: str, line: int, character: int) -> Any:
        req_id = self.send_request(
            "textDocument/completion",
            {"textDocument": {"uri": str(uri)}, "position": {"line": int(line), "character": int(character)}},
        )
        resp = self.recv_until(lambda msg: msg.get("id") == req_id, timeout=DEFAULT_TIMEOUT_S)
        if "error" in resp:
            raise AssertionError("completion failed: {}".format(resp.get("error")))
        return resp.get("result")

    def code_actions(self, *, uri: str, line: int, character: int) -> Any:
        req_id = self.send_request(
            "textDocument/codeAction",
            {
                "textDocument": {"uri": str(uri)},
                "range": {
                    "start": {"line": int(line), "character": int(character)},
                    "end": {"line": int(line), "character": int(character)},
                },
                "context": {"diagnostics": []},
            },
        )
        resp = self.recv_until(lambda msg: msg.get("id") == req_id, timeout=DEFAULT_TIMEOUT_S)
        if "error" in resp:
            raise AssertionError("codeAction failed: {}".format(resp.get("error")))
        return resp.get("result")

    def execute_command(self, command: str, arguments: List[Any]) -> Any:
        req_id = self.send_request(
            "workspace/executeCommand",
            {"command": str(command), "arguments": list(arguments)},
        )
        resp = self.recv_until(lambda msg: msg.get("id") == req_id, timeout=DEFAULT_TIMEOUT_S)
        if "error" in resp:
            raise AssertionError("executeCommand failed: {}".format(resp.get("error")))
        return resp.get("result")

    def send_request(self, method: str, params: Dict[str, Any]) -> int:
        msg_id = int(self._next_id)
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": msg_id, "method": str(method), "params": params})
        return msg_id

    def send_notification(self, method: str, params: Dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": str(method), "params": params})

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

        trace_tail = "\n".join(self._trace[-TRACE_KEEP_N:])
        stderr_tail = "".join(self._stderr_lines[-200:])
        raise AssertionError(
            "timeout waiting for LSP message\n--- trace (tail) ---\n{}\n--- stderr (tail) ---\n{}".format(trace_tail, stderr_tail)
        )

    def shutdown(self) -> None:
        if self._proc.poll() is not None:
            return

        try:
            shutdown_id = self.send_request("shutdown", {})
            _ = self.recv_until(lambda msg: msg.get("id") == shutdown_id, timeout=DEFAULT_TIMEOUT_S)
            self.send_notification("exit", {})
            self._stdin.close()
            self._proc.wait(timeout=DEFAULT_TIMEOUT_S)
        except Exception:  # noqa: BLE001
            self._proc.terminate()
            try:
                self._proc.wait(timeout=DEFAULT_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def _record(self, direction: str, msg: Dict[str, Any]) -> None:
        # Keep a compact tail for debugging on timeouts.
        compact = json.dumps(msg, ensure_ascii=False, sort_keys=True)
        self._trace.append("[{}] {}".format(direction, compact))
        if len(self._trace) > TRACE_KEEP_N:
            self._trace = self._trace[-TRACE_KEEP_N:]

    def _send(self, msg: Dict[str, Any]) -> None:
        self._record("send", msg)
        payload = _encode_lsp_message(msg)
        self._stdin.write(payload)
        self._stdin.flush()

    def _stdout_loop(self) -> None:
        while True:
            msg = _read_lsp_message(self._stdout)
            if msg is None:
                return
            self._record("recv", msg)
            if "id" in msg and "method" in msg and "result" not in msg and "error" not in msg:
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
            result: Dict[str, Any] = {"applied": bool(applied)}
            if reason:
                result["failureReason"] = str(reason)
            self._send({"jsonrpc": "2.0", "id": req_id, "result": result})
            return

        self._send({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "method not supported"}})

    def _stderr_loop(self) -> None:
        while True:
            line = self._stderr.readline()
            if not line:
                return
            self._stderr_lines.append(line.decode("utf-8", errors="replace"))


__all__ = [
    "LspSession",
    "start_yaml_dsl_lsp_server",
]
