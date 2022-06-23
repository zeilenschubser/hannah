from hannah.nas.dataflow.dataflow_utils import find_first_op_in_dfg
from hannah.nas.dataflow.tensor_expression import TensorExpression


class OpType(TensorExpression):
    def __init__(self, *operands, tensor_type=None, name="", **attributes):
        super().__init__(*operands, tensor_type=tensor_type, name=name)

        for name, attribute in attributes.items():
            setattr(self, name, attribute)

        self.attributes = attributes
        self.link_users()

    def link_users(self):
        for operand in self.operands:
            last_output = find_first_op_in_dfg(operand)
            last_output.users.append(self)

    def __repr__(self) -> str:
        return "Op({})".format(self.id)
