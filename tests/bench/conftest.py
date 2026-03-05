import sys

import pytest


def _find_verification_modules():
    return sorted(
        name for name in sys.modules if name.endswith("._verification") or "._verification." in name or name.endswith("_verification")
    )


@pytest.fixture(autouse=True)
def _forbid_verification_imports():
    pre = _find_verification_modules()
    if pre:
        pytest.fail("Bench tests must not import _verification modules: {0}".format(", ".join(pre)))

    yield

    post = _find_verification_modules()
    if post:
        pytest.fail("Bench tests must not import _verification modules: {0}".format(", ".join(post)))
