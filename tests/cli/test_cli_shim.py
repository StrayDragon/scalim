import types

import pytest

from scalim import _cli_shim


def test_cli_shim_main_returns_2_and_prints_help_when_cli_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _raise_import_error(_name: str):
        raise ImportError("nope")

    monkeypatch.setattr(_cli_shim.importlib, "import_module", _raise_import_error)

    assert _cli_shim.main(["--help"]) == 2

    captured = capsys.readouterr()
    assert "scalim-cli" in captured.err
    assert 'uv tool install "scalim[cli]"' in captured.err


def test_cli_shim_main_returns_2_when_cli_module_has_no_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(_cli_shim.importlib, "import_module", lambda _name: object())

    assert _cli_shim.main(["--help"]) == 2

    captured = capsys.readouterr()
    assert "scalim-cli" in captured.err


def test_cli_shim_main_delegates_to_scalim_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"argv": None}

    def _dummy_cli_main(argv):
        called["argv"] = argv
        return 7

    dummy_module = types.SimpleNamespace(main=_dummy_cli_main)
    monkeypatch.setattr(_cli_shim.importlib, "import_module", lambda _name: dummy_module)

    assert _cli_shim.main(["yaml-dsl", "validate", "config.yaml"]) == 7
    assert called["argv"] == ["yaml-dsl", "validate", "config.yaml"]
