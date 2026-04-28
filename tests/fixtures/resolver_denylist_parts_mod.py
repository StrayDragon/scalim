class Obj:
    @staticmethod
    def safe() -> str:
        return "safe"


def _lambda() -> str:
    return "lambda"


def _a__b() -> str:
    return "a__b"


setattr(Obj, "lambda", staticmethod(_lambda))
setattr(Obj, "a__b", staticmethod(_a__b))
