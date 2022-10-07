import textwrap
from abc import abstractmethod
from typing import Any

from hannah.nas.expressions.placeholder import Placeholder
from hannah.nas.parameters.parameters import Parameter
from hannah.nas.parameters.parametrize import parametrize

from ..core.expression import Expression
from ..core.parametrized import is_parametrized


class Op(Expression):
    @abstractmethod
    def evaluate(self):
        ...

    @abstractmethod
    def format(self, indent=2, length=80) -> str:
        ...

    def _evaluate_operand(self, current_lhs):
        if is_parametrized(current_lhs):
            current_lhs = current_lhs.current_value
        elif isinstance(current_lhs, Op):
            current_lhs = current_lhs.evaluate()
        elif isinstance(current_lhs, Placeholder):
            current_lhs = current_lhs.value
        return current_lhs

    def _format_operand(self, other: Any, indent: int, length: int) -> str:
        if isinstance(other, Op):
            return other.format(indent, length)
        return str(other)

    def set_scope(self, scope, name):
        def _recursive_scoping(expr, scope):
            if isinstance(expr, BinaryOp):
                _recursive_scoping(expr.lhs, scope)
                _recursive_scoping(expr.rhs, scope)
            elif isinstance(expr, UnaryOp):
                _recursive_scoping(expr.operand, scope)
            elif isinstance(expr, Parameter):
                if hasattr(expr, 'name') and expr.name:
                    expr.id = f'{scope}.{expr.name}'
                else:
                    expr.id = f'{scope}.{name}'

        _recursive_scoping(self, scope)


@parametrize
class BinaryOp(Op):
    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs
        self.symbol = type(self).__name__

    def format(self, indent=2, length=80):
        ret = "(" + self.symbol + "\n"
        ret += (
            textwrap.indent(
                self._format_operand(self.lhs, indent, length), " " * indent
            )
            + "\n"
        )
        ret += (
            textwrap.indent(
                self._format_operand(self.rhs, indent, length), " " * indent
            )
            + "\n"
        )
        ret += ")"
        return ret

    def __repr__(self):
        return type(self).__name__ + "(" + repr(self.lhs) + "," + repr(self.rhs) + ")"

    def evaluate(self):
        current_lhs = self.lhs
        current_rhs = self.rhs

        current_lhs = self._evaluate_operand(current_lhs)
        current_rhs = self._evaluate_operand(current_rhs)

        return self.concrete_impl(current_lhs, current_rhs)

    @abstractmethod
    def concrete_impl(self, lhs, rhs):
        ...


@parametrize
class UnaryOp(Op):
    def __init__(self, operand) -> None:
        super().__init__()
        self.operand = operand
        self.symbol = type(self).__name__

    def evaluate(self):
        current_operand = self._evaluate_operand(self.operand)
        return self.concrete_impl(current_operand)

    @abstractmethod
    def concrete_impl(self, operand):
        ...

    def format(self, indent=2, length=80):
        ret = "(" + self.symbol
        ret += " " + self._format_operand(self.operand) + ")"
        return ret
