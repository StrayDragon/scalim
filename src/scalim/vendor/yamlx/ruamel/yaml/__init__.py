# coding: utf-8

import sys

# NOTE: This `ruamel.yaml` tree is vendored under `scalim.vendor.yamlx`.
# Upstream code uses absolute imports like `from ruamel.yaml.* import ...` and
# `from _ruamel_yaml import ...`. To keep the vendored copy self-contained (and
# avoid accidentally importing `site-packages/ruamel`), we bootstrap minimal
# aliases in `sys.modules` at import-time.
_parent_name = __name__.rsplit(".", 1)[0]
_parent_pkg = sys.modules.get(_parent_name)
if _parent_pkg is not None:
    sys.modules["ruamel"] = _parent_pkg
sys.modules["ruamel.yaml"] = sys.modules[__name__]

try:
    from ... import _ruamel_yaml as _vendored_ruamel_yaml  # type: ignore
except Exception:  # noqa: BLE001
    pass
else:
    sys.modules["_ruamel_yaml"] = _vendored_ruamel_yaml

if False:  # MYPY
    from typing import Dict, Any  # NOQA

_package_data = dict(
    full_package_name='ruamel.yaml',
    version_info=(0, 18, 3),
    __version__='0.18.3',
    version_timestamp='2023-10-29 16:24:20',
    author='Anthon van der Neut',
    author_email='a.van.der.neut@ruamel.eu',
    description='ruamel.yaml is a YAML parser/emitter that supports roundtrip preservation of comments, seq/map flow style, and map key order',  # NOQA
    entry_points=None,
    since=2014,
    extras_require={
        ':platform_python_implementation=="CPython" and python_version<"3.13"': ['ruamel.yaml.clib>=0.2.7'],  # NOQA
        'jinja2': ['ruamel.yaml.jinja2>=0.2'],
        'docs': ['ryd', 'mercurial>5.7'],
    },
    classifiers=[
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Text Processing :: Markup',
        'Typing :: Typed',
    ],
    keywords='yaml 1.2 parser round-trip preserve quotes order config',
    read_the_docs='yaml',
    supported=[(3, 7)],  # minimum
    tox=dict(
        env='*',
        fl8excl='_test/lib,branch_default',
    ),
    # universal=True,
    python_requires='>=3',
)  # type: Dict[Any, Any]


version_info = _package_data['version_info']
__version__ = _package_data['__version__']

try:
    from .cyaml import *  # NOQA

    __with_libyaml__ = True
except (ImportError, ValueError):  # for Jython
    __with_libyaml__ = False

from ruamel.yaml.main import *  # NOQA
