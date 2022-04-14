import textwrap
from abc import ABC, abstractmethod
from typing import Any

import hannah.nas.parameters.parameters as p


class AbstractOp(ABC):
    @abstractmethod
    def evaluate(self):
        ...

    @abstractmethod
    def format(self, indent=2, length=80) -> str:
        ...

    def _get_formatted(self, other: Any, indent: int, length: int) -> str:
        if isinstance(other, AbstractOp):
            return other.format(indent, length)
        return str(other)

    def __str__(self) -> str:
        return self.format()


class AbstractArithmeticOp(AbstractOp):
    pass


class AbstractBinaryOp(AbstractArithmeticOp):
    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs
        self._symbol = self.__name__

    def format(self, indent=2, length=80):
        ret = "(" + self._symbol + "\n"
        ret += textwrap.indent(self._get_formatted(self.lhs), " " * indent) + "\n"
        ret += textwrap.indent(self._get_formatted(self.rhs), " " * indent) + "\n"
        ret += ")"
        return ret

    def __repr__(self):
        return self.__name__ + "(" + repr(lhs) + "," + repr(rhs) + ")"

    def evaluate(self):
        current_lhs = self.lhs
        current_rhs = self.rhs

        if isinstance(current_lhs, p.Parameter):
            current_lhs = current_lhs.current_value
        elif isinstance(current_lhs, AbstractArithmeticOp):
            current_lhs = current_lhs.evaluate()

        if isinstance(current_rhs, p.Parameter):
            current_rhs = current_rhs.current_value
        elif isinstance(current_rhs, AbstractArithmeticOp):
            current_rhs = current_rhs.evaluate()

        return self.concrete_impl(current_lhs, current_rhs)


class AbstractAdd(AbstractBinaryOp):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, rhs)
        self._symbol = "+"

    def concrete_impl(self, lhs, rhs):
        return lhs + rhs


class AbstractSub(AbstractBinaryOp):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, rhs)
        self._symbol = "-"

    def concrete_impl(self, lhs, rhs):
        return lhs - rhs


class AbstractMul(AbstractBinaryOp):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, rhs)
        self._symbol = "*"

    def concrete_impl(self, lhs, rhs):
        return lhs * rhs


class AbstractTruediv(AbstractBinaryOp):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, rhs)
        self._symbol = "/"

    def concrete_impl(self, lhs, rhs):
        return lhs / rhs


class AbstractFloordiv(AbstractBinaryOp):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, rhs)
        self._symbol = "//"

    def concrete_impl(self, lhs, rhs):
        return lhs // rhs


class AbstractMod(AbstractBinaryOp):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, rhs)
        self._symbol = "mod"

    def concrete_impl(self, lhs, rhs):
        return lhs % rhs


class AbstractAnd(AbstractBinaryOp):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, rhs)
        self._symbol = "and"

    def concrete_impl(self, lhs, rhs):
        # Fixme this does not follow python semantacics exactly
        return lhs and rhs


class AbstractOr(AbstractBinaryOp):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, rhs)
        self._symbol = "or"

    def concrete_impl(self, lhs, rhs):
        # Fixme this does not follow python semantacics exactly
        return lhs or rhs
