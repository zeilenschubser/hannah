import logging

import torch
import torch.nn.functional as F
import torch.utils.data as data

from torchmetrics.functional import accuracy
from torchmetrics.functional import precision
from torchmetrics.functional import recall
from torchmetrics.functional import f1

from hydra.utils import instantiate, get_class
from torchmetrics import ConfusionMatrix
from ..utils import set_deterministic

from .base import ClassifierModule

logger = logging.getLogger(__name__)


class ImageClassifierModule(ClassifierModule):
    def setup(self, stage):
        if self.logger:
            self.logger.log_hyperparams(self.hparams)

        if self.initialized:
            return

        self.initialized = True

        dataset_cls = get_class(self.hparams.dataset.cls)
        self.train_set, self.dev_set, self.test_set = dataset_cls.splits(
            self.hparams.dataset
        )
        self.example_input_array = torch.tensor(self.test_set[0][0]).unsqueeze(0)
        self.example_feature_array = torch.tensor(self.test_set[0][0]).unsqueeze(0)

        self.num_classes = len(self.train_set.class_names)

        logger.info("Setting up model %s", self.hparams.model.name)
        self.model = instantiate(
            self.hparams.model,
            labels=self.num_classes,
            input_shape=self.example_input_array.shape,
        )

        self.test_confusion = ConfusionMatrix(num_classes=self.num_classes)

    def get_class_names(self):
        return self.train_set.class_names

    def prepare_data(self):
        # get all the necessary data stuff
        if not self.train_set or not self.test_set or not self.dev_set:
            get_class(self.hparams.dataset.cls).prepare(self.hparams.dataset)

    def forward(self, x):
        return self.model(x)

    def _get_dataloader(self, dataset, shuffle=False):
        batch_size = self.hparams["batch_size"]
        dataset_conf = self.hparams.dataset
        sampler = None
        if shuffle:
            sampler_type = dataset_conf.get("sampler", "random")
            if sampler_type == "weighted":
                if self.hparams.dataset.default_weights:
                    sampler = self.get_balancing_sampler_with_weights(
                        dataset, self.hparams.dataset.weights
                    )
                else:
                    sampler = self.get_balancing_sampler(dataset)
            else:
                sampler = data.RandomSampler(dataset)

        train_loader = data.DataLoader(
            dataset,
            batch_size=batch_size,
            drop_last=True,
            num_workers=self.hparams["num_workers"],
            sampler=sampler,
            multiprocessing_context="fork" if self.hparams["num_workers"] > 0 else None,
        )

        self.batches_per_epoch = len(train_loader)

        return train_loader

    def training_step(self, batch, batch_idx):
        x, y = batch

        if batch_idx == 0:
            loggers = self._logger_iterator()

            for logger in loggers:
                if hasattr(logger.experiment, "add_image"):
                    import torchvision.utils

                    images = torchvision.utils.make_grid(x, normalize=True)
                    logger.experiment.add_image(f"input{batch_idx}", images)

        logits = self(x)
        if self.hparams.dataset.weighted_loss:
            loss = F.cross_entropy(
                logits,
                y.squeeze(),
                weight=torch.tensor(self.hparams.dataset.weights, device=self.device),
            )
        else:
            loss = F.cross_entropy(logits, y.squeeze())
        self.log("train_loss", loss)

        return loss

    def validation_step(self, batch, batch_idx):
        x, y = batch
        logits = self(x)
        if self.hparams.dataset.weighted_loss:
            loss = F.cross_entropy(
                logits,
                y.squeeze(),
                weight=torch.tensor(self.hparams.dataset.weights, device=self.device),
            )
        else:
            loss = F.cross_entropy(logits, y.squeeze())
        preds = torch.argmax(logits, dim=1)
        acc = accuracy(preds, y.squeeze())

        self.log("val_loss", loss)
        self.log("val_error", 1 - acc)
        self.log("val_accuracy", acc)

    def test_step(self, batch, batch_idx):
        x, y = batch
        logits = self(x)
        if self.hparams.dataset.weighted_loss:
            loss = F.cross_entropy(
                logits,
                y.squeeze(),
                weight=torch.tensor(self.hparams.dataset.weights, device=self.device),
            )
        else:
            loss = F.cross_entropy(logits, y.squeeze())
        preds = torch.argmax(logits, dim=1)
        softmax = F.softmax(logits, dim=1)
        acc = accuracy(preds, y.squeeze())

        with set_deterministic(False):
            self.test_confusion(preds, y)
        preds = preds.to("cpu")
        y = y.to("cpu")

        precision_micro = precision(preds, y)
        recall_micro = recall(preds, y)
        f1_micro = f1(preds, y)
        precision_macro = precision(
            preds, y, num_classes=self.num_classes, average="macro"
        )
        recall_macro = recall(preds, y, num_classes=self.num_classes, average="macro")
        f1_macro = f1(preds, y, num_classes=self.num_classes, average="macro")
        self.log("test_loss", loss)
        self.log("test_error", 1 - acc)
        self.log("test_accuracy", acc)
        self.log("test_precesion_micro", precision_micro)
        self.log("test_recall_micro", recall_micro)
        self.log("test_f1_micro", f1_micro)
        self.log("test_precesion_macro", precision_macro)
        self.log("test_recall_macro", recall_macro)
        self.log("test_f1_macro", f1_macro)

    def train_dataloader(self):
        return self._get_dataloader(self.train_set, shuffle=True)

    def test_dataloader(self):
        return self._get_dataloader(self.test_set)

    def val_dataloader(self):
        return self._get_dataloader(self.dev_set)

    def on_train_epoch_end(self):
        self.eval()
        self._log_weight_distribution()
        self.train()
