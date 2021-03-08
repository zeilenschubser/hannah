from dataclasses import dataclass
from typing import Any

from hydra.core.config_store import ConfigStore


cs = ConfigStore.instance()


@dataclass
class AdadeltaConf:
    _target_: str = "torch.optim.adadelta.Adadelta"
    lr: Any = 1.0
    rho: Any = 0.9
    eps: Any = 1e-06
    weight_decay: Any = 0


cs.store(group="optimizer", name="adadelta", node=AdadeltaConf())


@dataclass
class AdamConf:
    _target_: str = "torch.optim.adam.Adam"
    lr: Any = 0.001
    betas: Any = (0.9, 0.999)
    eps: Any = 1e-08
    weight_decay: Any = 0
    amsgrad: Any = False


cs.store(group="optimizer", name="adam", node=AdamConf())


@dataclass
class AdamaxConf:
    _target_: str = "torch.optim.adamax.Adamax"
    lr: Any = 0.002
    betas: Any = (0.9, 0.999)
    eps: Any = 1e-08
    weight_decay: Any = 0


cs.store(group="optimizer", name="adamax", node=AdamaxConf())


@dataclass
class AdamWConf:
    _target_: str = "torch.optim.adamw.AdamW"
    lr: Any = 0.005
    betas: Any = (0.9, 0.999)
    eps: Any = 1e-08
    weight_decay: Any = 1e-05
    amsgrad: Any = False


cs.store(group="optimizer", name="adamw", node=AdamWConf())


@dataclass
class ASGDConf:
    _target_: str = "torch.optim.asgd.ASGD"
    lr: Any = 0.01
    lambd: Any = 0.0001
    alpha: Any = 0.75
    t0: Any = 1000000.0
    weight_decay: Any = 0


cs.store(group="optimizer", name="asgd", node=ASGDConf())


@dataclass
class LBFGSConf:
    _target_: str = "torch.optim.lbfgs.LBFGS"
    lr: Any = 1
    max_iter: Any = 20
    max_eval: Any = None
    tolerance_grad: Any = 1e-07
    tolerance_change: Any = 1e-09
    history_size: Any = 100
    line_search_fn: Any = None


cs.store(group="optimizer", name="lbfgs", node=LBFGSConf())


@dataclass
class RMSpropConf:
    _target_: str = "torch.optim.rmsprop.RMSprop"
    lr: Any = 0.01
    alpha: Any = 0.99
    eps: Any = 1e-08
    weight_decay: Any = 0
    momentum: Any = 0
    centered: Any = False


cs.store(group="optimizer", name="rmsprop", node=RMSpropConf())


@dataclass
class RpropConf:
    _target_: str = "torch.optim.rprop.Rprop"
    lr: Any = 0.01
    etas: Any = (0.5, 1.2)
    step_sizes: Any = (1e-06, 50)


cs.store(group="optimizer", name="rprop", node=RpropConf())


@dataclass
class SGDConf:
    _target_: str = "torch.optim.sgd.SGD"
    lr: Any = 0.1  # _RequiredParameter
    momentum: Any = 0
    dampening: Any = 0
    weight_decay: Any = 0
    nesterov: Any = False


cs.store(group="optimizer", name="sgd", node=SGDConf())


@dataclass
class SparseAdamConf:
    _target_: str = "torch.optim.sparse_adam.SparseAdam"
    lr: Any = 0.001
    betas: Any = (0.9, 0.999)
    eps: Any = 1e-08


cs.store(group="optimizer", name="sparse_adam", node=SparseAdamConf())
