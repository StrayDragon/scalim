import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import scalim_yaml_dsl_lsp.cli as lsp_cli


def test_dump_discovery_emits_json_payload(tmp_path, capsys) -> None:
    yaml_path = tmp_path / "demo.yaml"
    yaml_path.write_text("loader: demo\n", encoding="utf-8")

    code = lsp_cli.main(["dump-discovery", str(yaml_path), "--json"])
    assert code == 0

    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload["project_root"] == str(tmp_path)
    assert payload["python_roots"] == [str(tmp_path)]
    assert payload["allowed_yaml_roots"] == [str(tmp_path)]
    assert payload.get("scalim_yaml_path") is None


def test_lsp_server_publishes_diagnostics_and_resolves_definition(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    module_path = workspace / "mymod.py"
    module_path.write_text(
        "\n".join(
            [
                "def myfunc() -> int:",
                '    """demo docstring"""',
                "    return 1",
                "",
            ]
        ),
        encoding="utf-8",
    )

    yaml_path = workspace / "demo.yaml"
    yaml_text = "loader: mymod:myfunc\n"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp
        assert "result" in init_resp

        client.send_notification("initialized", {})

        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )

        pub = client.recv_until(
            lambda msg: msg.get("method") == "textDocument/publishDiagnostics",
            timeout=10.0,
        )
        assert pub["params"]["uri"] == yaml_path.as_uri()

        line0 = yaml_text.splitlines()[0]
        cursor_char = int(line0.index("mymod")) + 1
        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": 0, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp

        locations = definition_resp.get("result") or []
        assert isinstance(locations, list)
        assert any(loc.get("uri") == module_path.as_uri() for loc in locations)
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


class _LspClient:
    def __init__(self, proc: subprocess.Popen[bytes]) -> None:
        if proc.stdin is None or proc.stdout is None or proc.stderr is None:
            raise RuntimeError("unexpected: subprocess pipes not available")
        self._proc = proc
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

        raise AssertionError("timeout waiting for LSP message; stderr:\n{}".format("".join(self._stderr_lines[-50:])))

    def shutdown(self) -> None:
        if self._proc.poll() is not None:
            return

        try:
            shutdown_id = self.send_request("shutdown", {})
            _ = self.recv_until(lambda msg: msg.get("id") == shutdown_id, timeout=5.0)
            self.send_notification("exit", {})
            self._stdin.close()
            self._proc.wait(timeout=5.0)
        except Exception:  # noqa: BLE001
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def _send(self, msg: Dict[str, Any]) -> None:
        payload = _encode_lsp_message(msg)
        self._stdin.write(payload)
        self._stdin.flush()

    def _stdout_loop(self) -> None:
        while True:
            msg = _read_lsp_message(self._stdout)
            if msg is None:
                return
            self._inbox.put(msg)

    def _stderr_loop(self) -> None:
        while True:
            line = self._stderr.readline()
            if not line:
                return
            self._stderr_lines.append(line.decode("utf-8", errors="replace"))
