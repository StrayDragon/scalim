import re
from typing import FrozenSet

__all__ = ()

EXCEL_SHEET_NAME_MAX_LEN = 31
EXCEL_SHEET_NAME_INVALID_CHARS: FrozenSet[str] = frozenset(["\\", "/", "?", "*", "[", "]", ":"])

OUTPUT_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validation_error_message(*, path: str, reason: str, hint: str) -> str:
    return "{}: {}. Hint: {}".format(str(path), str(reason), str(hint))


def validate_excel_sheet_name(sheet: str, *, path: str) -> None:
    """校验 `Excel` 工作表名(`sheet_name`)的稳定输入契约.

    注意:
    - 该规则属于 `SSOT`: `workflow compile`/`runtime compile`/`internal parser`/`CLI validate` 等入口必须保持一致.
    - 报错信息必须统一模板并包含 `Hint:`.
    """

    name = str(sheet or "").strip()
    invalid_chars_hint = "\\ / ? * [ ] :"
    if not name:
        raise ValueError(
            _validation_error_message(
                path=str(path),
                reason="Excel sheet name must be non-empty",
                hint="provide a non-empty string (max_len={}; invalid chars: {}).".format(
                    int(EXCEL_SHEET_NAME_MAX_LEN),
                    invalid_chars_hint,
                ),
            )
        )

    if len(name) > int(EXCEL_SHEET_NAME_MAX_LEN):
        raise ValueError(
            _validation_error_message(
                path=str(path),
                reason="Excel sheet name is too long: len={} > {}".format(len(name), int(EXCEL_SHEET_NAME_MAX_LEN)),
                hint="use a shorter name (max_len={}).".format(int(EXCEL_SHEET_NAME_MAX_LEN)),
            )
        )

    invalid = sorted(set(name).intersection(EXCEL_SHEET_NAME_INVALID_CHARS))
    if invalid:
        raise ValueError(
            _validation_error_message(
                path=str(path),
                reason="Excel sheet name contains invalid characters: {}".format("".join(invalid)),
                hint="remove the invalid characters: {}.".format(invalid_chars_hint),
            )
        )


def validate_output_name(name: str, *, path: str) -> None:
    """校验 `outputs[*].name` 的稳定输入契约(标识符规则)."""

    value = str(name or "").strip()
    if not value:
        raise ValueError(
            _validation_error_message(
                path=str(path),
                reason="Output name must be non-empty",
                hint="provide an identifier like [a-zA-Z_][a-zA-Z0-9_]*.",
            )
        )
    if not OUTPUT_NAME_PATTERN.match(value):
        raise ValueError(
            _validation_error_message(
                path=str(path),
                reason="Invalid identifier {!r}".format(value),
                hint="expected [a-zA-Z_][a-zA-Z0-9_]*.",
            )
        )
