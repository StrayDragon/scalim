from pathlib import Path


def tests_root() -> Path:
    return Path(__file__).resolve().parents[1]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def fixtures_dir() -> Path:
    return tests_root() / "fixtures"


__all__ = [
    "fixtures_dir",
    "repo_root",
    "tests_root",
]
