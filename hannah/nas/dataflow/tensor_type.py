from .tensor_expression import TensorExpression
from hannah.nas.parameters.parametrize import parametrize
from ..hardware_description.memory_type import MemoryType
from .quantization_type import QuantizationType
from .data_type import DataType
from .axis_type import AxisType
from typing import Optional, Tuple


@parametrize
class TensorType:
    def __init__(
        self,
        axis: Tuple[AxisType, ...],
        dtype: DataType,
        quantization: Optional[QuantizationType] = None,
        memory: Optional[MemoryType] = None,
        name: str = "",
    ):
        self.axis = {}
        for ax in axis:
            self.axis[ax.name] = ax
        self.dtype = dtype
        self.quantization = quantization
        self.memory = memory
        self.name = name
        self.id = name

    def dim(self) -> int:
        return len(self.axis)

    def shape(self) -> Tuple[int, ...]:
        return tuple((ax.size for ax in self.axis.values))

    def __getitem__(self, key):
        return self.axis[key]

    def __repr__(self) -> str:
        # return 'Tensor(name=' + self.name + ", axis=(" + ' '.join(['{}, '.format(a) for a in self.axis.keys()]) + '))'
        return "TensorType({})".format(self.name)


# OutputType = Union[TensorType, TensorTuple]
