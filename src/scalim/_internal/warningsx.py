class ScalimExperimentalWarning(UserWarning):
    """项目内实验性行为告警类别.

    约定使用 `warnings.warn(..., category=ScalimExperimentalWarning)` 发出,便于调用方按类别过滤或升级为异常.
    """


__all__ = []
