import re
import sys
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple, cast
from urllib.parse import unquote, urlparse

from ..vendor.compact.typing_extensionsx import override

DEFAULT_SCHEMA_SERVE_HOST = "0.0.0.0"  # noqa: S104
DEFAULT_SCHEMA_SERVE_PORT = 62831

DEFAULT_SCHEMA_TYPE = "demand"
DEFAULT_SCHEMA_PATH = "http://localhost:62831"

DEFAULT_MAX_SCAN_LINES = 10

_SCHEMA_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")

_INTELLIJ_SCHEMA_PATTERN = re.compile(r"^\s*#\s*\$schema\s*:\s*(?P<ref>.*)\s*$")
_YAML_LANGUAGE_SERVER_SCHEMA_PATTERN = re.compile(r"^\s*#\s*yaml-language-server\s*:\s*\$schema\s*=\s*(?P<ref>.*)\s*$")


def schema_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "dsl" / "by_yaml" / "schema"


def list_schema_filenames(schema_dir_path: Path) -> List[str]:
    return sorted(p.name for p in schema_dir_path.glob("*.gen.json") if p.is_file())


def resolve_schema_ref(schema_type: str, schema_path: str) -> str:
    schema_type = (schema_type or "").strip() or DEFAULT_SCHEMA_TYPE
    if not _SCHEMA_TYPE_PATTERN.match(schema_type):
        msg = "Invalid schema type: {}".format(schema_type)
        raise ValueError(msg)

    schema_path = (schema_path or "").strip() or DEFAULT_SCHEMA_PATH
    schema_filename = "{}.gen.json".format(schema_type)

    if schema_path.endswith(".json"):
        return schema_path

    if schema_path.startswith(("http://", "https://")):
        base_url = schema_path.rstrip("/")
        return "{}/{}".format(base_url, schema_filename)

    base_dir = Path(schema_path)
    return str(base_dir / schema_filename)


def make_schema_modeline(schema_ref: str) -> str:
    return "# $schema: {}".format(schema_ref)


def _is_schema_modeline(line: str) -> bool:
    return bool(_INTELLIJ_SCHEMA_PATTERN.match(line) or _YAML_LANGUAGE_SERVER_SCHEMA_PATTERN.match(line))


def upsert_schema_modeline_text(
    text: str,
    *,
    schema_modeline: str,
    max_scan_lines: int = DEFAULT_MAX_SCAN_LINES,
) -> Tuple[str, bool]:
    newline = "\r\n" if "\r\n" in text else "\n"
    ends_with_newline = text.endswith("\n")

    lines = text.splitlines()
    scan_limit = min(len(lines), max_scan_lines)

    modeline_indices: List[int] = []
    for idx in range(scan_limit):
        line = lines[idx]
        stripped = line.strip()

        if _is_schema_modeline(line):
            modeline_indices.append(idx)
            continue

        if not stripped:
            continue

        if stripped.startswith("#"):
            continue

        break

    changed = False
    if modeline_indices:
        first_idx = modeline_indices[0]
        if lines[first_idx] != schema_modeline:
            lines[first_idx] = schema_modeline
            changed = True
        for idx in reversed(modeline_indices[1:]):
            _ = lines.pop(idx)
            changed = True
    else:
        lines = [schema_modeline, "", *lines]
        changed = True

    new_text = newline.join(lines)
    if ends_with_newline:
        new_text += newline

    return new_text, changed


@dataclass
class UpsertResult:
    path: Path
    changed: bool
    error: Optional[str] = None


def upsert_schema_modeline_file(
    path: Path,
    *,
    schema_modeline: str,
    max_scan_lines: int = DEFAULT_MAX_SCAN_LINES,
) -> UpsertResult:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return UpsertResult(path=path, changed=False, error="Failed to read: {}".format(exc))

    new_text, changed = upsert_schema_modeline_text(text, schema_modeline=schema_modeline, max_scan_lines=max_scan_lines)
    if not changed:
        return UpsertResult(path=path, changed=False)

    try:
        _ = path.write_text(new_text, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return UpsertResult(path=path, changed=False, error="Failed to write: {}".format(exc))

    return UpsertResult(path=path, changed=True)


class _ReusableHTTPServer(HTTPServer):
    allow_reuse_address: bool = True


def _extract_single_filename(raw_path: str) -> Optional[str]:
    parsed = urlparse(raw_path)
    path = unquote(parsed.path or "")
    if path.startswith("/"):
        path = path[1:]
    if not path:
        return None
    if "/" in path or "\\" in path:
        return None
    return path


class SchemaHTTPServer(_ReusableHTTPServer):
    schema_dir_path: Path
    allowed_names: Set[str]

    def __init__(
        self,
        server_address: Tuple[str, int],
        handler_cls: type,
        *,
        schema_dir_path: Path,
        allowed_names: Set[str],
    ) -> None:
        self.schema_dir_path = schema_dir_path
        self.allowed_names = allowed_names
        super().__init__(server_address, handler_cls)


class SchemaHandler(BaseHTTPRequestHandler):
    server_version: str = "scalim-cli-schema-serve"

    def do_GET(self) -> None:
        filename = self._resolve_schema_filename()
        if filename is None:
            self._send_not_found()
            return

        schema_path = self._schema_dir_path() / filename
        if not schema_path.exists() or not schema_path.is_file():
            self._send_not_found()
            return

        try:
            payload = schema_path.read_bytes()
        except Exception:  # noqa: BLE001
            self._send_not_found()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        _ = self.wfile.write(payload)

    def do_HEAD(self) -> None:
        filename = self._resolve_schema_filename()
        if filename is None:
            self._send_not_found()
            return

        schema_path = self._schema_dir_path() / filename
        if not schema_path.exists() or not schema_path.is_file():
            self._send_not_found()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()

    def do_POST(self) -> None:
        self._send_method_not_allowed()

    def do_PUT(self) -> None:
        self._send_method_not_allowed()

    def do_DELETE(self) -> None:
        self._send_method_not_allowed()

    @override
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        message = format % args
        _ = sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), message))

    def _schema_dir_path(self) -> Path:
        server = cast("SchemaHTTPServer", self.server)
        return server.schema_dir_path

    def _resolve_schema_filename(self) -> Optional[str]:
        server = cast("SchemaHTTPServer", self.server)
        filename = _extract_single_filename(self.path)
        if filename is None:
            return None
        if filename not in server.allowed_names:
            return None
        if not filename.endswith(".gen.json"):
            return None
        return filename

    def _send_not_found(self) -> None:
        self.send_response(404)
        self.end_headers()

    def _send_method_not_allowed(self) -> None:
        self.send_response(405)
        self.end_headers()


def create_schema_http_server(
    *,
    host: str,
    port: int,
    schema_dir_path: Optional[Path] = None,
) -> Tuple[SchemaHTTPServer, int, List[str]]:
    schema_dir_path = schema_dir_path or schema_dir()
    allowed_names = list_schema_filenames(schema_dir_path)
    server = SchemaHTTPServer(
        (host, port),
        SchemaHandler,
        schema_dir_path=schema_dir_path,
        allowed_names=set(allowed_names),
    )
    actual_port = int(server.server_address[1])
    return server, actual_port, allowed_names


def print_schema_serve_banner(*, host: str, port: int, schema_filenames: Sequence[str]) -> None:
    base_url = "http://localhost:{}".format(port)
    _ = sys.stdout.write("正在提供 `YAML DSL` 的 `JSON Schema` 文件: {}\n".format(schema_dir()))
    _ = sys.stdout.write("监听地址: http://{}:{}\n".format(host, port))
    _ = sys.stdout.write("推荐 `$schema` 基址: {}\n".format(base_url))
    _ = sys.stdout.write("可用的 `schema` 文件:\n")
    for name in schema_filenames:
        _ = sys.stdout.write("- {}/{}\n".format(base_url, name))
    if schema_filenames:
        _ = sys.stdout.write("头部示例:\n")
        _ = sys.stdout.write("{}\n".format(make_schema_modeline("{}/{}".format(base_url, schema_filenames[0]))))
