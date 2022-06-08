from typing import Optional

from ..core.expression import Expression


class Placeholder(Expression):
    def __init__(self, name: Optional[str] = None):
        self.name = name
        self._conditions = []

    def evaluate(self):
        raise NotImplementedError()

    def cond(self, condition):
        self._conditions.append(condition)

    def format(self, indent=2, length=80) -> str:
        return self.__class__.__name__ + "()"


class UndefinedInt(Placeholder):
    def __init__(self, name: Optional[str] = None) -> None:
        super().__init__(name)


# TODO:
class UndefinedFloat(Placeholder):
    def __init__(self, name: Optional[str] = None) -> None:
        super().__init__(name)


class DefaultInt(Placeholder):
    def __init__(self, value: int, name: Optional[str] = None) -> None:
        super().__init__(name)
        self.value = value


class DefaultFloat(Placeholder):
    def __init__(self, value: float, name: Optional[str] = None) -> None:
        super().__init__(name)
        self.value = value


class IntRange(Placeholder):
    def __init__(self, lower: int, upper: int, name: Optional[str] = None) -> None:
        super().__init__(name)
        self.upper = upper
        self.lower = lower


class FloatRange(Placeholder):
    def __init__(self, lower: int, upper: int, name: Optional[str] = None):
        super().__init__(name)
        self.lower = lower
        self.upper = upper


class Categorical(Placeholder):
    def __init__(self, name: Optional[str] = None):
        super().__init__(name)
