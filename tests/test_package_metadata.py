import scalim


def test_package_version_metadata_is_exposed() -> None:
    assert isinstance(scalim.__version__, str)
    assert scalim.__version__
    assert scalim.__version__ == scalim._project_constants.VERSION

