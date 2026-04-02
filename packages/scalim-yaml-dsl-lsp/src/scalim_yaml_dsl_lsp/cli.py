import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional, Sequence

from .core import discover_yaml_dsl_editor_project

__all__ = ()

try:
    from .server import create_server as _create_server
except Exception:  # noqa: BLE001
    _create_server = None


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="scalim-yaml-dsl-lsp")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Start YAML DSL LSP server (default: stdio).")
    serve_parser.add_argument("--tcp", action="store_true", help="Start server in TCP mode (debug-only).")
    serve_parser.add_argument("--host", default="127.0.0.1", help="TCP bind host (default: 127.0.0.1).")
    serve_parser.add_argument("--port", type=int, default=2087, help="TCP bind port (default: 2087).")
    serve_parser.add_argument("--log-file", default="", help="Write logs to a file instead of stderr.")
    serve_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level (DEBUG/INFO/WARNING/ERROR). Default: INFO.",
    )

    dump_parser = subparsers.add_parser("dump-discovery", help="Dump editor project discovery payload for a YAML file.")
    dump_parser.add_argument("yaml_path", help="Path to a YAML file.")
    dump_parser.add_argument("--json", action="store_true", help="Print JSON payload to stdout.")

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "dump-discovery":
        return _cmd_dump_discovery(args.yaml_path, as_json=bool(args.json))

    if args.command == "serve":
        return _cmd_serve(
            tcp=bool(args.tcp),
            host=str(args.host),
            port=int(args.port),
            log_file=str(args.log_file or ""),
            log_level=str(args.log_level or "INFO"),
        )

    parser.error("未知命令")
    return 2


def _configure_logging(*, log_file: str, log_level: str) -> None:
    level = getattr(logging, str(log_level or "INFO").upper(), logging.INFO)
    handlers = []
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    else:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=level,
        handlers=handlers,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _cmd_dump_discovery(yaml_path: str, *, as_json: bool) -> int:
    try:
        discovery = discover_yaml_dsl_editor_project(Path(str(yaml_path)))
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("[错误] `dump-discovery` 失败: {}: {}\n".format(type(exc).__name__, exc))
        return 2

    payload = discovery.as_dict()
    if not as_json:
        sys.stdout.write("{}\n".format(payload))
        return 0

    sys.stdout.write("{}\n".format(json.dumps(payload, ensure_ascii=False, indent=2)))
    return 0


def _cmd_serve(*, tcp: bool, host: str, port: int, log_file: str, log_level: str) -> int:
    _configure_logging(log_file=log_file, log_level=log_level)

    if _create_server is None:
        sys.stderr.write("[错误] `LSP` 服务端依赖缺失,请安装 `scalim-yaml-dsl-lsp[server]`.\n")
        return 2

    server = _create_server()

    try:
        if tcp:
            server.start_tcp(host, int(port))
        else:
            server.start_io()
    except Exception as exc:
        logging.getLogger(__name__).exception("`LSP` 服务端启动失败: %s", type(exc).__name__)
        sys.stderr.write("[错误] `LSP` 服务端启动失败: {}: {}\n".format(type(exc).__name__, exc))
        return 2
    return 0
