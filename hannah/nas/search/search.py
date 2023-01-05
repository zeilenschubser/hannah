#
# Copyright (c) 2022 University of Tübingen.
#
# This file is part of hannah.
# See https://atreus.informatik.uni-tuebingen.de/ties/ai/hannah/hannah for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import logging
from joblib import Parallel, delayed
import numpy as np
from omegaconf import OmegaConf
import torch
import os

from abc import ABC, abstractmethod
from copy import deepcopy
from pathlib import Path
from hydra.utils import instantiate, get_class
import yaml
from hannah.callbacks.optimization import HydraOptCallback
from hannah.nas.search.model_trainer.parallel_model_trainer import ParallelModelTrainer
from hannah.nas.search.sampler.aging_evolution import AgingEvolution
from hannah.nas.search.utils import WorklistItem
from hannah.utils.utils import common_callbacks
from hannah.nas.graph_conversion import model_to_graph

msglogger = logging.getLogger(__name__)

class NASBase(ABC):
    def __init__(self,
                 budget=2000,
                 parent_config=None) -> None:
        self.budget = budget
        self.config = parent_config
        self.callbacks = []

    def run(self):
        self.before_search()
        self.search()
        self.after_search()

    @abstractmethod
    def before_search(self):
        pass

    @abstractmethod
    def search(self):
        pass

    @abstractmethod
    def after_search(self):
        pass

    def add_model_trainer(self, trainer):
        self.model_trainer = trainer


class DirectNAS(NASBase):
    def __init__(self,
                 budget=2000,
                 *args,
                 **kwargs) -> None:
        super().__init__(*args, budget=budget, **kwargs)

    def before_search(self):
        # setup logging
        self.initialize_dataset()
        self.search_space = self.build_search_space()

    def search(self):
        for i in range(self.budget):
            self.global_num = i
            self.setup_model_logging()
            parameters = self.sample()
            model = self.build_model(parameters)
            lightning_module = self.initialize_lightning_module(model)
            self.train_model(lightning_module)

            self.log_results(lightning_module)
    def after_search(self):
        self.extract_best_model()

    def build_model(self, parameters):
        # FIXME: use parameters
        model = deepcopy(self.search_space)
        model.initialize()
        return model

    def build_search_space(self):
        search_space = instantiate(self.config.model)
        return search_space


    def initialize_lightning_module(self, model):
        module = instantiate(
                self.config.module,
                model=model,
                dataset=self.config.dataset,
                optimizer=self.config.optimizer,
                features=self.config.features,
                normalizer=self.config.get("normalizer", None),
                scheduler=self.config.scheduler,
                example_input_array=self.example_input_array,
                num_classes=len(self.train_set.class_names),
                _recursive_=False,
            )
        return module

    def initialize_dataset(self):
        get_class(self.config.dataset.cls).prepare(self.config.dataset)

        # Instantiate Dataset
        train_set, val_set, test_set = get_class(self.config.dataset.cls).splits(
            self.config.dataset
        )

        self.train_set = train_set
        self.val_set = val_set
        self.test_set = test_set
        self.example_input_array = torch.rand([1] + train_set.size())

    def train_model(self, model):
        trainer = instantiate(self.config.trainer, callbacks=self.callbacks)
        trainer.fit(model)

    def sample(self):
        # FIXME: Decoupled sampling
        self.search_space.sample()

    def setup_model_logging(self):
        self.callbacks = common_callbacks(self.config)
        opt_monitor = self.config.get("monitor", ["val_error", "train_classifier_loss"])
        opt_callback = HydraOptCallback(monitor=opt_monitor)
        self.result_handler = opt_callback
        self.callbacks.append(opt_callback)

    def log_results(self, module):
        from networkx.readwrite import json_graph
        nx_model = model_to_graph(module.model, module.example_feature_array)
        json_data = json_graph.node_link_data(nx_model)
        if not os.path.exists("../performance_data"):
            os.mkdir("../performance_data")
        with open(f"../performance_data/model_{self.global_num}.json", "w") as res_file:
            import json

            json.dump(
                {"graph": json_data,
                 "hparams": {"batch_size": int(self.config.module.batch_size)},
                             "metrics": self.result_handler.result(dict=True),
                             "curves": self.result_handler.curves(dict=True)},
                res_file,
            )

class AgingEvolutionNAS(DirectNAS):
    def __init__(self,
                 budget=2000,
                 parametrization=None,
                 bounds=None,
                 random_state=None,
                 population_size=100,
                 presample=True,
                 n_jobs=10,
                 *args, **kwargs) -> None:
        super().__init__(budget, *args, **kwargs)
        self.random_state = np.random.RandomState()
        self.optimizer = AgingEvolution(parametrization=parametrization,
                                        bounds=bounds,
                                        population_size=population_size,
                                        random_state=self.random_state)
        self.presample = presample
        self.worklist = []
        self.model_trainer = ParallelModelTrainer()
        self.n_jobs=n_jobs

    def sample(self):
        parameters = self.optimizer.next_parameters()
        return parameters

    def build_search_space(self):
        pass

    def build_model(self, parameters):
        config = OmegaConf.merge(self.config, parameters.flatten())
        try:
            # setup the model
            model = instantiate(
                config.module,
                dataset=config.dataset,
                model=config.model,
                optimizer=config.optimizer,
                features=config.features,
                scheduler=config.get("scheduler", None),
                normalizer=config.get("normalizer", None),
                _recursive_=False,
            )
            model.setup("train")
        except AssertionError as e:
            msglogger.critical(
                "Instantiation failed. Probably #input/output channels are not divisible by #groups!"
            )
            msglogger.critical(str(e))
        else:
            estimated_metrics = {}
            # estimated_metrics = self.predictor.estimate(model)

            satisfied_bounds = []
            for k, v in estimated_metrics.items():
                if k in self.bounds:
                    distance = v / self.bounds[k]
                    msglogger.info(f"{k}: {float(v):.8f} ({float(distance):.2f})")
                    satisfied_bounds.append(distance <= 1.2)

            worklist_item = WorklistItem(parameters, estimated_metrics)

            if self.presample:
                if all(satisfied_bounds):
                    self.worklist.append(worklist_item)
            else:
                self.worklist.append(worklist_item)

    def search(self):
        print("Begin Search")
        with Parallel(n_jobs=self.n_jobs) as executor:
            while len(self.optimizer.history) < self.budget:
                self.worklist = []
                # Mutate current population
                while len(self.worklist) < self.n_jobs:
                    parameters = self.sample()
                    self.build_model(parameters)

                # validate population
                configs = [
                    OmegaConf.merge(self.config, item.parameters.flatten())
                    for item in self.worklist
                ]

                results = executor(
                    [
                        delayed(self.model_trainer.run_training)(
                            num,
                            len(self.optimizer.history) + num,
                            OmegaConf.to_container(config, resolve=True),
                        )
                        for num, config in enumerate(configs)
                    ]
                )

                for num, (config, result) in enumerate(zip(configs, results)):
                    nas_result_path = Path("results")
                    if not nas_result_path.exists():
                        nas_result_path.mkdir(parents=True, exist_ok=True)
                    config_file_name = f"config_{len(self.optimizer.history)+num}.yaml"
                    config_path = nas_result_path / config_file_name
                    with config_path.open("w") as config_file:
                        config_file.write(OmegaConf.to_yaml(config))

                    result_path = nas_result_path / "results.yaml"
                    result_history = []
                    if result_path.exists():
                        with result_path.open("r") as result_file:
                            result_history = yaml.safe_load(result_file)
                        if not isinstance(result_history, list):
                            result_history = []

                    result_history.append(
                        {"config": str(config_file_name), "metrics": result}
                    )

                    with result_path.open("w") as result_file:
                        yaml.safe_dump(result_history, result_file)

                for result, item in zip(results, self.worklist):
                    parameters = item.parameters
                    metrics = {**item.results, **result}
                    for k, v in metrics.items():
                        metrics[k] = float(v)

                    self.optimizer.tell_result(parameters, metrics)






class WeightSharingNAS(NASBase):
    def __init__(self,
                 budget=2000) -> None:
        super().__init__(budget)