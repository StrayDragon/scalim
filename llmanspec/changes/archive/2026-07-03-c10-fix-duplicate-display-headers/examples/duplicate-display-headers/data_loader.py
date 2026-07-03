"""脱敏内存 loader: 返回占位假数据,每列值各不相同便于验证数据不错位。

本文件为 MVP 例子的一部分,不含任何真实业务数据。
"""

from typing import Any, Dict, List, Optional


def load_metrics(
    field_keys: Optional[List[str]] = None,
    is_ref_loader: bool = False,
    **_kwargs: Any,
) -> List[Dict[str, Any]]:
    """返回单行占位指标数据。

    四个字段的值各不相同(7 / 13111.26 / 1 / 10510.00),
    若导出时第 3/4 列被首列值填充(7 / 13111.26),即可一眼识别数据错位 bug。
    """

    _ = field_keys, is_ref_loader
    return [
        {
            "pay_count_first": 7,
            "pay_amount_first": 13111.26,
            "pay_count_repeat": 1,
            "pay_amount_repeat": 10510.00,
        },
    ]
