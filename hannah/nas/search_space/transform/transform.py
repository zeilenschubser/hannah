import hydra
from omegaconf import DictConfig
import torch
import torch.nn as nn
from hannah.models.factory import qat as qat
from hannah.nas.search_space.symbolic_operator import Context, SymbolicOperator
from hannah.nas.search_space.torch_converter import FunctionWrapper
from hannah.nas.search_space.modules.primitive_operators import Add, MergedModule

from hannah.nas.search_space.tcresnet.tcresnet_space import TCResNetSpace
from hannah.nas.search_space.pruner import Pruner
from hannah.nas.search_space.symbolic_constraint_solver import SymbolicConstrainer
from hannah.nas.search_space.utils import get_random_cfg
import networkx as nx
# from hannah.models.factory.qconfig import get_trax_qat_qconfig
from torch.quantization import default_qconfig


class Transformer:
    def __init__(self, space) -> None:
        """Tranformer class
        Performs transformation passes on the given space.
        The transform passes are performed in_place.

        Parameters
        ----------
        space : hannah.nas.search_space.symbolic_space.Space
            space that is to be transformed
        """
        self.space = space

    def transform_nodes(self, node_map, rules={}, attr_map={}, **kwargs):
        """Search for all occurences of a node in the space and
        replace it with another type of node. Occurences
        are defined over the target_cls of the SymOp node.

        Parameters
        ----------
        node_map : dict
            map from source class to target class -> {source_cls: target_cls}
        rules : dict, optional
            additional rules to further specify source nodes, e.g.
            search for a specific function in a wrapper class, by default {}
        attr_map : dict, optional
            maps the attributes (possibly NAS searchable) from source
            to target class, e.g. , by default {}
        """
        for node in self.space.nodes:
            if node.target_cls in node_map and self.check_rules(node, rules):
                node.target_cls = node_map[node.target_cls]
                new_params = {}
                for key, value in node.params.items():
                    if node.target_cls in attr_map and key in attr_map[node.target_cls]:
                        new_params[attr_map[node.target_cls][key]] = node.params[key]
                for key, value in kwargs.items():
                    new_params[key] = value
                node.params = new_params

    def transform_node_sequence(self, source, target, target_names={}, rules={}, attr_map={}, additional_attrs={}):
        """Transform occurences of a source node sequence to a target
        sequence

        Parameters
        ----------
        source : list
            source node sequence
        target : list
            target node sequence
        target_names : dict, optional
            mapping of {target_cls: alternative_name}
            in case one does not want to use the str(class_name), by default {}
        rules : dict, optional
            additional rules to further specify source nodes, e.g.
            search for a specific function in a wrapper class, by default {}, by default {}
        attr_map : dict, optional
            maps the attributes (possibly NAS searchable) from source
            to target class, Format:
            {target_cls : {key in target_cls: (source_cls, key in source_cls)}} e.g.,
            {qat.ConvBnReLU1d: {'in_channels':  (nn.Conv1d, 'in_channels')}}, by default {}
        additional_attrs : dict, optional
            additional attributes to the target classes. Format:
            {target_cls : {key in target_cls: value}}, by default {}
        """
        new_edges = []
        to_delete = []
        ct = 0
        for node in nx.topological_sort(self.space):
            found_sequence = False
            if node.target_cls == source[0] and self.check_rules(node, rules):
                sequence = {}
                found_sequence = self.check_path(node, source, rules, sequence)

            if found_sequence:
                attrs = {}
                for target_class, mapping in attr_map.items():
                    attrs[target_class] = {}
                    for target_key, source_value in mapping.items():
                        attrs[target_class][target_key] = sequence[source_value[0]].params[source_value[1]]

                for target_class, mapping in additional_attrs.items():
                    for key, value in mapping.items():
                        attrs[target_class][key] = value

                new_nodes = []
                for tar in target:
                    if tar not in target_names:
                        name = str(tar).split('.')[-1].split('\'')[0] + '_{}'.format(ct)
                    else:
                        name = target_names[tar]

                    new_node = SymbolicOperator(name=name,
                                                target_cls=tar,
                                                **attrs[tar])
                    new_nodes.append(new_node)
                ct += 1

                new_edges.append((list(self.space.in_edges(node))[0][0], new_nodes[0]))
                new_edges.append((new_nodes[-1], list(self.space.out_edges(sequence[source[-1]]))[0][1]))
                to_delete.extend(sequence.values())

        self.space.remove_nodes_from(to_delete)
        self.space.add_edges_from(new_edges)

    def merge_nodes(self, sequence_to_merge, rules={}):
        """Search for a sequence and replace it with a single
        merged node

        Parameters
        ----------
        sequence_to_merge : list
            sequence of target classes to merge
        rules : dict, optional
            additional rules to further specify source nodes, e.g.
            search for a specific function in a wrapper class, by default {}, by default {}
        """
        name = ''
        args = {}
        for mod in sequence_to_merge:
            cls_str = str(mod).split('.')[-1].split('\'')[0]
            name += cls_str
        target = MergedModule

        new_edges = []
        to_delete = []
        ct = 0
        for node in nx.topological_sort(self.space):
            found_sequence = False
            if node.target_cls == sequence_to_merge[0] and self.check_rules(node, rules):
                sequence = {}
                found_sequence = self.check_path(node, sequence_to_merge, rules, sequence)
            if found_sequence:
                args = {}
                module_classes = {}
                for mod, symop in sequence.items():
                    for k, v in symop.params.items():
                        args[symop.name + '.' + k] = v
                    module_classes[symop.name] = mod

                merged_node = SymbolicOperator(name=name + '_{}'.format(ct),
                                               target_cls=target,
                                               module_classes=module_classes,
                                               **args)
                ct += 1

                new_edges.append((list(self.space.in_edges(node))[0][0], merged_node))
                new_edges.append((merged_node, list(self.space.out_edges(sequence[sequence_to_merge[-1]]))[0][1]))
                to_delete.extend(sequence.values())

        self.space.remove_nodes_from(to_delete)
        self.space.add_edges_from(new_edges)

    def check_rules(self, node, rules):
        """For a given node, check possible additional rules
        rule[node] should be a function that receives a node and
        returns True if the rule applies, else False
        Parameters
        ----------
        node : SymbolicOperator
        rules : dict
            rules[node] = [rule1, rule2, ....]

        Returns
        -------
        bool
        """
        marker = True
        if node.target_cls not in rules:
            return marker
        for rule in rules[node.target_cls]:
            marker = rule(node)
            if not marker:
                return marker
        return marker

    def check_path(self, start_node, path, rules, sequence):
        if len(path) > 1 and start_node.target_cls == path[0] and self.check_rules(start_node, rules):
            out_edges = list(self.space.out_edges(start_node))
            if len(out_edges) > 1:
                return False  # matching with path forking not supported
            v = out_edges[0][1]
            sequence[path[0]] = start_node
            return self.check_path(v, path[1:], rules, sequence)
        elif len(path) == 1 and start_node.target_cls == path[0] and self.check_rules(start_node, rules):
            sequence[path[0]] = start_node
            return True
        else:
            return False


@hydra.main(config_name="config", config_path="../../../conf")
def main(config: DictConfig):
    space = TCResNetSpace(config, parameterization=True)
    transformer = Transformer(space)

    def is_add(node):
        return True if 'function' in node.params and node.params['function'] == 'add' else False

    node_map = {FunctionWrapper: Add}
    rules = {}
    rules[FunctionWrapper] = [is_add]

    pruner = Pruner(space)
    channel_constrainer = SymbolicConstrainer(space)
    cfg = get_random_cfg(space.get_config_dims())
    cfg = channel_constrainer.constrain_output_channels(cfg)
    x = torch.ones([1, 40, 101])
    cfg = pruner.find_next_valid_config(x, cfg, exclude_keys=['out_channels', 'kernel_size', 'dilation'])
    ctx = Context(cfg)
    instance_1, out_1 = space.infer_parameters(x, ctx, verbose=True)
    instance_1.eval()
    out_1 = instance_1(x)

    transformer.transform_nodes(node_map, rules)
    ctx = Context(cfg)
    instance_2, out_2 = space.infer_parameters(x, ctx, verbose=True)
    state_dict = instance_1.state_dict()
    instance_2.load_state_dict(state_dict)
    instance_2.eval()
    out_2 = instance_2(x)

    torch.testing.assert_allclose(out_2, out_1)
    print("Testing transform_nodes() successfull")

    source_sequence = [nn.Conv1d, nn.BatchNorm1d, nn.ReLU]
    target_sequence = [qat.ConvBnReLU1d]

    # Format:
    # {target_cls : {key in target node: (source_cls, key in source_sequence)}}
    attr_map = {qat.ConvBnReLU1d: {'in_channels':  (nn.Conv1d, 'in_channels'),
                                   'out_channels': (nn.Conv1d, 'out_channels'),
                                   'kernel_size':  (nn.Conv1d, 'kernel_size'),
                                   'stride':       (nn.Conv1d, 'stride'),
                                   'padding':      (nn.Conv1d, 'padding'),
                                   'dilation':     (nn.Conv1d, 'dilation'),
                                   'eps':          (nn.BatchNorm1d, 'eps'),
                                   'momentum':     (nn.BatchNorm1d, 'momentum')}
                }
    additional_attrs = {qat.ConvBnReLU1d: {'qconfig': default_qconfig,
                                           'out_quant': False}
                        }

    transformer.transform_node_sequence(source_sequence,
                                        target_sequence,
                                        attr_map=attr_map,
                                        additional_attrs=additional_attrs)

    pruner = Pruner(space)
    channel_constrainer = SymbolicConstrainer(space)
    cfg = get_random_cfg(space.get_config_dims())
    cfg = channel_constrainer.constrain_output_channels(cfg)
    cfg = pruner.find_next_valid_config(x, cfg, exclude_keys=['out_channels', 'kernel_size', 'dilation'])
    ctx = Context(cfg)
    instance, out = space.infer_parameters(x, ctx, verbose=True)
    print(out.shape)
    print("Testing transform_node_sequence() successfull")

    sequence_to_merge = [nn.Conv1d, nn.BatchNorm1d, nn.Hardtanh]
    transformer.merge_nodes(sequence_to_merge=sequence_to_merge)
    pruner = Pruner(space)
    channel_constrainer = SymbolicConstrainer(space)
    cfg = get_random_cfg(space.get_config_dims())
    cfg = channel_constrainer.constrain_output_channels(cfg)
    cfg = pruner.find_next_valid_config(x, cfg, exclude_keys=['out_channels', 'kernel_size', 'dilation'])
    ctx = Context(cfg)
    instance, out = space.infer_parameters(x, ctx, verbose=True)
    print(out.shape)
    print("Testing merge_nodes() successfull")

    print("Passed all tests")


if __name__ == '__main__':
    main()
