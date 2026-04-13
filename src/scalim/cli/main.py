# pragma: allow-non-core-file boundary: cli surface may migrate out; not part of core coverage gate
import argparse
from typing import List, Optional

from . import yaml_dsl


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scalim-cli", description="Scalim CLI")

    def _show_help(_args: argparse.Namespace) -> int:
        parser.print_help()
        return 2

    parser.set_defaults(func=_show_help)
    subparsers = parser.add_subparsers(dest="command")
    yaml_dsl.register(subparsers)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)  # type: ignore[attr-defined]


if __name__ == "__main__":
    raise SystemExit(main())

__all__ = ()
