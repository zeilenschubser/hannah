import torch
from sympy import solve, symbols
from hannah.nas.search_space.tcresnet.tcresnet_space import TCResNetSpace
import hydra
from omegaconf import DictConfig
from hannah.nas.search_space.symbolic_operator import Context
import torch.nn as nn
from hannah.nas.search_space.utils import get_random_cfg, flatten_config
import networkx as nx


class SymbolicConstrainer:
    def __init__(self, space) -> None:
        self.space = space
        self.solution = None

    def constrain_output_channels(self, cfg, set_to_values={}):
        constraints = []
        sym_map = {}
        for node in nx.topological_sort(self.space):
            name = '{}_{}'.format(node.name, 'out_channels')
            sym_map[name] = symbols(name, integer=True)
            in_edges = self.space.in_edges(node)
            channel_names = []
            if 'add' in node.name:
                for u, v in in_edges:
                    channel_names.append('{}_{}'.format(u.name, 'out_channels'))
                constraints.append(sym_map[channel_names[0]] - sym_map[channel_names[1]])  # channels of inputs have to be equal
                constraints.append(sym_map[channel_names[0]] - sym_map[name])  # out_channels of add itself are equal to first input
            elif node.target_cls != nn.Conv1d:
                for u, v in in_edges:
                    channel_names.append('{}_{}'.format(u.name, 'out_channels'))
                constraints.append(sym_map[name] - sym_map[channel_names[0]])  # outputchannels are unchanged
            elif node.target_cls == nn.Conv1d:
                pass

        for key, value in set_to_values.items():
            constraints.append(sym_map[key] - value)

        cfg_dims = self.space.get_config_dims()
        sol = solve(constraints)

        for node, params in cfg_dims.items():
            for k, v in params.items():
                if k == 'out_channels':
                    name = '{}_{}'.format(node, 'out_channels')
                    if sym_map[name] in sol and not sol[sym_map[name]].is_symbol:
                        val = int(sol[sym_map[name]])
                        constraints.append(sym_map[name] - val)
                        cfg[node][k] = val
                    else:
                        val = cfg[node][k]
                        constraints.append(sym_map[name] - val)
            sol = solve(constraints)
        return cfg


@hydra.main(config_name="config", config_path="../../conf")
def main(config: DictConfig):

    space = TCResNetSpace(config, parameterization=True)
    constrainer = SymbolicConstrainer(space)
    cfg = get_random_cfg(space.get_config_dims())
    cfg = constrainer.constrain_output_channels(cfg)
    values = list(flatten_config(cfg).values())
    print(values)
    ctx = Context(cfg)
    x = torch.ones([1, 40, 101])
    instance, out = space.infer_parameters(x, ctx, verbose=True)
    print(out.shape)

    # cfg['layers_1_downsample_0']['out_channels'] = 98
    # values = list(flatten_config(ctx.config).values())
    # print(values)
    # cfg = constrainer.constrain_output_channels(cfg, set_to_values={'layers_1_downsample_0_out_channels': 122})
    cfg = constrainer.constrain_output_channels(cfg, set_to_values={'layers_1_convs_3_out_channels': 67})
    ctx = Context(cfg)
    values = list(flatten_config(ctx.config).values())
    print(values)
    instance, out = space.infer_parameters(x, ctx, verbose=True)
    print(out.shape)


if __name__ == '__main__':
    main()
