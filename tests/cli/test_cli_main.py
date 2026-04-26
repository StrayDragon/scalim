"""``scalim-cli`` 主入口点烟雾测试."""

import scalim_cli.main as cli_main


def test_build_parser_creates_subcommands() -> None:
    parser = cli_main._build_parser()  # noqa: SLF001
    assert parser.prog == "scalim-cli"

    choices = set()
    for action in parser._subparsers._actions:  # noqa: SLF001
        if hasattr(action, "choices") and action.choices:
            choices.update(action.choices.keys())

    assert "yaml-dsl" in choices
    assert "log" in choices


def test_main_returns_2_for_no_args() -> None:
    rc = cli_main.main([])
    assert rc == 2


def test_main_help_flag(capsys: object) -> None:
    import pytest

    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["--help"])
    assert exc_info.value.code == 0
