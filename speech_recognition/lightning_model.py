from pytorch_lightning.core.lightning import LightningModule
from pytorch_lightning.metrics.functional import accuracy, f1_score, recall
from .config_utils import (
    get_loss_function,
    get_optimizer,
    get_model,
    save_model,
    get_lr_scheduler,
)
from .utils import _locate
from .dataset import ctc_collate_fn

import torch
import torch.utils.data as data
from pytorch_lightning import TrainResult, EvalResult


class SpeechClassifierModule(LightningModule):
    def __init__(self, config=None, log_dir="", msglogger=None):
        super().__init__()
        # torch.autograd.set_detect_anomaly(True)
        # TODO lit logger to saves hparams (also outdated to use)
        # which causes error TypeError: can't pickle int objects
        self.hparams = config

        # model
        self.train_set, self.dev_set, self.test_set = _locate(
            config["dataset_cls"]
        ).splits(config)
        self.hparams["width"] = self.train_set.width
        self.hparams["height"] = self.train_set.height
        self.model = get_model(self.hparams)

        # loss function
        self.criterion = get_loss_function(self.model, self.hparams)
        self.log_dir = log_dir
        self.msglogger = msglogger
        self.msglogger.info("speech classifier initialized")

        # summarize model architecture
        dummy_width, dummy_height = self.train_set.width, self.train_set.height
        dummy_input = torch.zeros(1, dummy_height, dummy_width)
        self.example_input_array = dummy_input
        self.bn_frozen = False

    # PREPARATION
    def configure_optimizers(self):
        optimizer = get_optimizer(self.hparams, self)
        scheduler = get_lr_scheduler(self.hparams, optimizer)

        return [optimizer], [scheduler]

    def get_batch_metrics(self, output, y):

        if isinstance(output, list):
            output = torch.mean(torch.stack(output), dim=0)

        y = y.view(-1)

        output_max = output.argmax(dim=1)
        batch_acc = accuracy(output_max, y, self.hparams["n_labels"])
        batch_f1 = f1_score(output_max, y)
        batch_recall = recall(output_max, y)

        return batch_acc, batch_f1, batch_recall

    # TRAINING CODE
    def training_step(self, batch, batch_idx):

        x, x_len, y, y_len = batch
        output = self(x)
        y = y.view(-1)
        loss = self.criterion(output, y)

        # --- after loss
        for callback in self.trainer.callbacks:
            if hasattr(callback, "on_before_backward"):
                callback.on_before_backward(self.trainer, self, loss)
        # --- before backward

        # METRICS
        batch_acc, batch_f1, batch_recall = self.get_batch_metrics(output, y)

        result = TrainResult(loss)

        log_vals = {
            "train_loss": loss,
            "train_acc": batch_acc,
            "train_f1": batch_f1,
            "train_recall": batch_recall,
        }

        # TODO sync across devices in case of multi gpu via kwarg sync_dist=True
        result.log_dict(log_vals, on_step=True, on_epoch=True)

        return result

    def train_dataloader(self):

        train_batch_size = self.hparams["batch_size"]
        train_loader = data.DataLoader(
            self.train_set,
            batch_size=train_batch_size,
            shuffle=True,
            drop_last=True,
            pin_memory=True,
            num_workers=self.hparams["num_workers"],
            collate_fn=ctc_collate_fn,
        )

        self.batches_per_epoch = len(train_loader)

        return train_loader

    # VALIDATION CODE

    def validation_step(self, batch, batch_idx):

        # dataloader provides these four entries per batch
        x, x_length, y, y_length = batch

        # INFERENCE
        output = self.model(x)
        y = y.view(-1)
        loss = self.criterion(output, y)

        # METRICS
        batch_acc, batch_f1, batch_recall = self.get_batch_metrics(output, y)
        result = EvalResult(loss)
        log_vals = {
            "val_loss": loss,
            "val_acc": batch_acc,
            "val_f1": batch_f1,
            "val_recall": batch_recall,
        }

        # TODO sync across devices in case of multi gpu via kwarg sync_dist=True
        result.log_dict(log_vals)

        return result

    def val_dataloader(self):

        dev_loader = data.DataLoader(
            self.dev_set,
            batch_size=min(len(self.dev_set), 16),
            shuffle=False,
            num_workers=self.hparams["num_workers"],
            collate_fn=ctc_collate_fn,
        )

        return dev_loader

    # TEST CODE
    def test_step(self, batch, batch_idx):

        # dataloader provides these four entries per batch
        x, x_length, y, y_length = batch

        output = self.model(x)
        y = y.view(-1)
        loss = self.criterion(output, y)

        # METRICS
        batch_acc, batch_f1, batch_recall = self.get_batch_metrics(output, y)

        # RESULT DICT
        result = EvalResult(loss)
        log_vals = {
            "test_loss": loss,
            "test_acc": batch_acc,
            "test_f1": batch_f1,
            "test_recall": batch_recall,
        }

        # TODO sync across devices in case of multi gpu via kwarg sync_dist=True
        result.log_dict(log_vals)

        return result

    def test_dataloader(self):

        test_loader = data.DataLoader(
            self.test_set,
            batch_size=1,
            shuffle=False,
            num_workers=self.hparams["num_workers"],
            collate_fn=ctc_collate_fn,
        )

        return test_loader

    # FORWARD (overwrite to train instance of this class directly)
    def forward(self, x):
        return self.model(x)

    # CALLBACKS
    def on_train_end(self):
        # TODO currently custom save, in future proper configure lighting for saving ckpt
        save_model(
            self.log_dir,
            self.model,
            self.test_set,
            config=self.hparams,
            msglogger=self.msglogger,
        )
