# force-en
"""Local stdlib HTTP mock for hook/event scenario demos.

Endpoints:
- ``POST /upload`` — accept export upload metadata (+ optional body bytes)
- ``POST /dispatch`` — sync/async routing decision from estimated_rows
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_DEFAULT_ASYNC_ROWS_THRESHOLD = 100


@dataclass
class MockHttpState:
    uploads: List[Dict[str, Any]] = field(default_factory=list)
    upload_attempts: List[Dict[str, Any]] = field(default_factory=list)
    dispatches: List[Dict[str, Any]] = field(default_factory=list)
    async_rows_threshold: int = _DEFAULT_ASYNC_ROWS_THRESHOLD
    upload_failures_remaining: int = 0
    upload_fail_status: int = 503


class _Handler(BaseHTTPRequestHandler):
    state: MockHttpState

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        _ = (format, args)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            msg = "JSON body must be an object"  # force-en
            raise ValueError(msg)
        return data

    def _write_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        path = str(self.path).split("?", 1)[0]
        try:
            if path == "/upload":
                payload = self._read_json()
                if int(self.state.upload_failures_remaining) > 0:
                    self.state.upload_failures_remaining = int(self.state.upload_failures_remaining) - 1
                    status = int(self.state.upload_fail_status)
                    self.state.upload_attempts.append({"ok": False, "status": status, "payload": dict(payload)})
                    self._write_json(status, {"ok": False, "error": "transient", "status": status})
                    return
                self.state.uploads.append(dict(payload))
                self.state.upload_attempts.append({"ok": True, "status": 200, "payload": dict(payload)})
                self._write_json(200, {"ok": True, "received": len(self.state.uploads)})
                return
            if path == "/dispatch":
                payload = self._read_json()
                estimated_rows = int(payload.get("estimated_rows") or 0)
                mode = "async" if estimated_rows >= int(self.state.async_rows_threshold) else "sync"
                record = {"request": dict(payload), "mode": mode}
                self.state.dispatches.append(record)
                self._write_json(200, {"mode": mode, "estimated_rows": estimated_rows})
                return
            self._write_json(404, {"ok": False, "error": "not_found", "path": path})
        except Exception as exc:  # noqa: BLE001
            self._write_json(400, {"ok": False, "error": type(exc).__name__, "message": str(exc)})


@dataclass
class MockHttpServer:
    host: str
    port: int
    state: MockHttpState
    _httpd: HTTPServer
    _thread: threading.Thread

    @property
    def base_url(self) -> str:
        return "http://{}:{}".format(self.host, int(self.port))

    def stop(self) -> None:
        self._httpd.shutdown()
        self._thread.join(timeout=5.0)
        self._httpd.server_close()


def start_mock_http_server(
    *,
    async_rows_threshold: int = _DEFAULT_ASYNC_ROWS_THRESHOLD,
    upload_failures_remaining: int = 0,
    upload_fail_status: int = 503,
) -> MockHttpServer:
    state = MockHttpState(
        async_rows_threshold=int(async_rows_threshold),
        upload_failures_remaining=int(upload_failures_remaining),
        upload_fail_status=int(upload_fail_status),
    )

    class BoundHandler(_Handler):
        pass

    BoundHandler.state = state
    httpd = HTTPServer(("127.0.0.1", 0), BoundHandler)
    host, port = httpd.server_address[:2]
    thread = threading.Thread(target=httpd.serve_forever, name="scalim-hooks-events-mock-http", daemon=True)
    thread.start()
    return MockHttpServer(host=str(host), port=int(port), state=state, _httpd=httpd, _thread=thread)


def _post_json(url: str, payload: Dict[str, Any], *, timeout: float = 5.0) -> Tuple[int, Dict[str, Any]]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — local mock only
            raw = resp.read()
            status = int(getattr(resp, "status", 200) or 200)
    except HTTPError as exc:
        raw = exc.read() if exc.fp is not None else b"{}"
        status = int(exc.code)
    except URLError as exc:
        msg = "mock http request failed: {}".format(exc)  # force-en
        raise RuntimeError(msg) from exc  # force-en
    data = json.loads(raw.decode("utf-8") or "{}")
    if not isinstance(data, dict):
        data = {"raw": data}
    return status, data


def post_upload(base_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    status, data = _post_json("{}/upload".format(base_url.rstrip("/")), payload)
    if status != 200:
        msg = "upload failed status={} body={!r}".format(status, data)  # force-en
        raise RuntimeError(msg)  # force-en
    return data


def post_upload_with_status(base_url: str, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    return _post_json("{}/upload".format(base_url.rstrip("/")), payload)


def post_dispatch(base_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    status, data = _post_json("{}/dispatch".format(base_url.rstrip("/")), payload)
    if status != 200:
        msg = "dispatch failed status={} body={!r}".format(status, data)  # force-en
        raise RuntimeError(msg)  # force-en
    return data


def build_upload_payload(*, target_id: str, output_path: Optional[str], row_count: int) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "target_id": str(target_id),
        "output_path": None if output_path is None else str(output_path),
        "row_count": int(row_count),
        "size": 0,
        "content_sha1": None,
    }
    if output_path:
        try:
            with open(output_path, "rb") as f:
                data = f.read()
            payload["size"] = len(data)
            payload["content_sha1"] = hashlib.sha1(data).hexdigest()  # noqa: S324
        except OSError:
            payload["size"] = 0
            payload["content_sha1"] = None
    return payload
