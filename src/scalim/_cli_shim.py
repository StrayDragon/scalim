import importlib
import sys
from typing import List, Optional


def _print_cli_missing_message() -> None:
    python_version = "{}.{}.{}".format(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
    message_lines = [
        "[error] scalim CLI is not available in this environment.",
        "",
        "- The CLI lives in the optional package: `scalim-cli` (requires Python >= 3.10).",
        "- Current Python: {}".format(python_version),
        "",
        "Install (recommended):",
        '  uv tool install "scalim[cli]"',
        "",
        "Or install the standalone CLI package:",
        "  uv tool install scalim-cli",
        "",
        "Run once without installing:",
        '  uvx --from "scalim[cli]" scalim-cli <args...>',
        "",
    ]
    _ = sys.stderr.write("\n".join(message_lines))


def main(argv: Optional[List[str]] = None) -> int:
    try:
        module = importlib.import_module("scalim_cli.main")
    except (ImportError, SyntaxError):
        _print_cli_missing_message()
        return 2

    try:
        cli_main = module.main
    except AttributeError:
        _print_cli_missing_message()
        return 2

    return int(cli_main(argv))


__all__ = ()
