from copy import deepcopy
import inspect
from typing import Optional
from hannah.nas.core.expression import Expression
from hannah.nas.core.parametrized import is_parametrized
from hannah.nas.parameters.parameters import Parameter
from inspect import Parameter as P


def _create_parametrize_wrapper(params, cls):
    parameter_list = list(params.values())
    old_init_fn = cls.__init__

    def init_fn(self, *args, **kwargs):
        self._PARAMETERS = {}
        self._annotations = {}
        self._conditions = []

        num = 1
        tuple_idx = 0
        for arg in args:
            if is_parametrized(arg):
                name = parameter_list[num].name
                if parameter_list[num].kind == P.VAR_POSITIONAL:
                    name = name + f'_{tuple_idx}'
                    tuple_idx += 1
                else:
                    num += 1
                self._PARAMETERS[name] = arg
                # self._annotations[name] = parameter_list[num + 1]._annotation
        print()
        for name, arg in kwargs.items():
            if is_parametrized(arg):
                self._PARAMETERS[name] = arg
                # self._annotations[name] = params[name]._annotation

        # TODO:
        cls.sample = sample
        cls.set_current = set_current
        cls.instantiate = instantiate
        cls.check = check
        cls.set_params = set_params
        cls.parameters = parameters
        cls.get_parameters = get_parameters
        cls.set_param_scopes = set_param_scopes
        cls.cond = cond
        self._parametrized = True
        old_init_fn(self, *args, **kwargs)

    return init_fn


def parametrize(cls=None):
    def parametrize_function(cls):
        init_fn = cls.__init__
        init_sig = inspect.signature(init_fn)

        new_init_fn = _create_parametrize_wrapper(init_sig.parameters, cls)
        cls.__init__ = new_init_fn

        return cls

    if cls:
        return parametrize_function(cls)

    return parametrize_function


def sample(self):
    for _key, param in self._PARAMETERS.items():
        param.sample()


def set_current(self, value):
    self.set_params(**value)
    self.check(None)  # argument "value" not needed currently


def set_params(self, **kwargs):
    for key, value in kwargs.items():
        assert key in self._PARAMETERS, "{} has no parameter {}".format(self, key)

        if not isinstance(value, dict) and key in self._annotations and not isinstance(value, self._annotations[key]):
            raise TypeError('Value must be of type {} but is {}'.format(self._annotations[key], type(value)))
        if is_parametrized(value):
            self._PARAMETERS[key] = value
            setattr(self, key, value)  # TODO: Do we want this to work?
        else:
            self._PARAMETERS[key].set_current(value)


def check(self, value):
    for con in self._conditions:
        if not con.evaluate():
            raise Exception("Condition not satisfied: {}".format(con))


def cond(self, condition):
    self._conditions.append(condition)


def instantiate(self):
    instance = deepcopy(self)
    instance._parametrized = False
    self.check(None)

    for key, param in instance._PARAMETERS.items():
        instantiated_value = param.instantiate()
        instance._PARAMETERS[key] = instantiated_value
        setattr(instance, key, instantiated_value)
    return instance


def get_parameters(self, scope: Optional[str] = None):
    params = {}
    visited = []
    queue = []
    queue.extend(self._PARAMETERS.values())

    while queue:
        current = queue.pop(-1)
        visited.append(current.id)
        params[current.id] = current

        if hasattr(current, '_PARAMETERS'):
            for param in current._PARAMETERS.values():
                if param.id not in visited:
                    queue.append(param)

    params = hierarchical_parameter_dict(params)
    return params


def parameters(self):
    return self.get_parameters()


def set_param_scopes(self):
    for name, param in self._PARAMETERS.items():
        if isinstance(param, Expression):
            param.id = self.id + '.' + name


def hierarchical_parameter_dict(parameter):
    hierarchical_params = {}
    for key, param in parameter.items():
        key_list = key.split('.')
        current_param_branch = hierarchical_params

        for k in key_list:
            try:
                index = int(k)
                if index not in current_param_branch:
                    current_param_branch[index] = {}
                current_param_branch = current_param_branch[index]
            except Exception:
                if k not in current_param_branch:
                    current_param_branch[k] = {}
                current_param_branch = current_param_branch[k]
            if k == key_list[-1] and isinstance(param, Parameter):
                current_param_branch[k] = param
    return hierarchical_params
