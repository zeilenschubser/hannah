from typing import Iterable
from hannah.nas.dataflow.op_type import OpType
from hannah.nas.dataflow.tensor import TensorTuple
from hannah.nas.dataflow.dataflow_utils import find_first_op_in_dfg, find_leaf_nodes
from hannah.nas.dataflow.tensor_expression import TensorExpression
from hannah.nas.dataflow.tensor import Tensor
from hannah.nas.expressions.placeholder import DefaultInt


class DataFlowGraph(TensorExpression):
    def __init__(self, *operands, output, name: str = "dataflow") -> None:
        super().__init__(*operands, tensor_type=None, name=name)
        self.inputs = []
        self.operand_to_input_map = {}
        # For each operand, an input placeholder tensor is created
        # operand_to_input_map serves as an convenient place to store the
        # respective affiliations (used e.g. in link_users())
        # FIXME: Do we REALLY need the placeholders?
        if self.operands:
            for i, o in enumerate(self.operands):
                inp = Tensor(name='input')
                self.inputs.append(inp)
                self.operand_to_input_map[o] = inp

        self.output = output
        self.link_users()
        self._scopes = {}
        self.set_scope_ids()

    def link_users(self):
        """ Link the DFG to its users and the users of the DFG to
        the DFG
        """
        def _rewire_to_placeholder(operand, node, placeholder):
            """ Delete the link "operand.user = node" that was formed
            when the node was instantiated (FIXME: Empty DFGs?) and add
            the link "placeholder.user = node". Recursively
            traverse the current subgraph to find the correct node
            (node that has the operand which we want to rewire)


            Parameters
            ----------
            operand : TensorExpression
                operand that we want to rewire
            node : TensorExpression
                node which uses the operand
            placeholder : Tensor
                input placeholder of the DFG
            """
            if operand in node.operands:
                last_output = find_first_op_in_dfg(operand)
                last_output.users.remove(node)

                placeholder.users.append(node)
            elif isinstance(node, DataFlowGraph):
                _rewire_to_placeholder(operand, node.output, placeholder)
            elif isinstance(node, OpType):
                for o in node.operands:
                    _rewire_to_placeholder(operand, o, placeholder)

        for operand, corresponding_placeholder in self.operand_to_input_map.items():
            last_output = find_first_op_in_dfg(operand)
            last_output.users.append(self)
            self.users.append(corresponding_placeholder)
            _rewire_to_placeholder(operand, self.output, corresponding_placeholder)

    def set_scope_ids(self, visited=[]):
        node = find_first_input(self)
        current_scope = update_scope(node, [])
        counters = {}
        queue = [node]
        visited.append(node)

        while queue:
            node = queue.pop(-1)
            current_scope = update_scope(node, current_scope)
            scope_id = get_id_and_update_counters(current_scope, counters)
            node.set_id(scope_id)
            self._scopes[scope_id] = node

            leafs = []
            find_leaf_nodes(node, leafs, visited)

            while leafs:
                leaf = leafs.pop(-1)
                current_scope = update_scope(leaf, current_scope)
                scope_id = get_id_and_update_counters(current_scope, counters)
                leaf.set_id(scope_id)
                self._scopes[scope_id] = leaf

            for u in node.users:
                if u not in visited:
                    queue = [u] + queue
                    visited.append(u)

    def output_tensor(self):
        return self.output.output_tensor()

    def __getitem__(self, key):
        return self._scopes[key]

    def __repr__(self) -> str:
        return "DataFlowGraph(id={})".format(self.id)


def dataflow(func):
    def wrapper_func(*args, **kwargs):
        name = func.__name__
        operands = args
        for key, value in kwargs.items():
            if isinstance(value, int):
                kwargs[key] = DefaultInt(value)
        output = func(*args, **kwargs)

        if isinstance(output, Iterable):
            output = TensorTuple(output, name=name+".output")

        dfg = DataFlowGraph(*operands, output=output, name=name)
        return dfg

    return wrapper_func


# FIXME: I'd rather have these methods in a different place but
# one has to be careful to avoid circular imports. This works for now.
def get_id_and_update_counters(current_scope, counters):
    if len(current_scope) > 1:
        scope = '.'.join([current_scope[-2].id, current_scope[-1].name])
    else:
        scope = current_scope[-1].name
    if scope not in counters:
        counters[scope] = 0
    else:
        counters[scope] += 1

    return '{}.{}'.format(scope, counters[scope])


def update_scope(node, current_scope):
    to_remove = []
    for scope in current_scope:
        if isinstance(scope, Tensor):
            to_remove.append(scope)
        elif isinstance(scope, OpType) and node in scope.users:
            to_remove.append(scope)
        elif isinstance(scope, OpType) and scope not in collect_users(node):
            to_remove.append(scope)
        elif isinstance(scope, DataFlowGraph) and scope in node.operands:
            to_remove.append(scope)

    new_scope = []
    for s in current_scope:
        if s not in to_remove:
            new_scope.append(s)
        else:
            # if a scope is removed, all lower-hierarchy scopes
            # are removed too because we assume strictly nested scopes
            # i.e. not overlapping
            break
    new_scope.append(node)
    return new_scope


def collect_users(node):
    collected_users = []
    queue = [node]
    visited = []

    while queue:
        node = queue.pop(-1)
        for u in node.users:
            if u not in visited:
                queue = [u] + queue
                visited.append(u)
                collected_users.append(u)

    return collected_users


def reset_scope_ids(node):
    node.set_id(node.name)
    for o in node.operands:
        reset_scope_ids(o)


def find_first_input(node):
    """Recusively traverses the graph from the given node
    back to its first input. NOTE: The traversal is via OPERANDS
    and not OUTPUT, meaning that e.g. weight Tensors that are
    included in Ops in a DFG are not returned

    Parameters
    ----------
    node : _type_
        _description_

    Returns
    -------
    _type_
        _description_
    """
    if node.operands:
        for o in node.operands:
            return find_first_input(o)
    else:
        return node
