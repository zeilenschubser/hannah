import logging
import math
from typing import Any, Mapping, Tuple, Union

import timm
import torch
import torch.nn as nn
from torch import nn

import hydra

logger = logging.getLogger(__name__)


class DefaultAnomalyDetector(nn.Module):
    def __init__(self, latent_shape):
        self.pooling = nn.AdaptiveAvgPool2d((1, 1))
        self.flatten = nn.Flatten()
        self.linear = nn.LazyLinear(1)

    def forward(self, x):
        x = self.pooling(x)
        x = self.flatten(x)
        x = self.linear(x)
        x = nn.functional.sigmoid(x)

        return x


class DefaultClassifierHead(nn.Module):
    def __init__(self, latent_shape, num_classes):
        super().__init__()

        self.pooling = nn.AdaptiveAvgPool2d((1, 1))
        self.flatten = nn.Flatten()
        self.linear = nn.LazyLinear(num_classes)

    def forward(self, x):
        x = self.pooling(x)
        x = self.flatten(x)
        x = self.linear(x)
        return x


class DefaultDecoderHead(nn.Module):
    def __init__(self, latent_shape, input_shape):
        """Default Decoder Head for autoencoders tousing Conv2D and Upsample

        Args:
            latent_shape (Tuple): Shape (CxHxW) of the latent representation of the autoencoder
            input_shape (Tuple): Shape (CxHxW) of the reconstructed image
        """
        super().__init__()

        input_x = input_shape[-2]
        input_y = input_shape[-1]
        input_channels = input_shape[-3]

        latent_x = latent_shape[-2]
        latent_y = latent_shape[-1]

        scale_factor_x = math.log2(input_x / latent_x)
        scale_factor_y = math.log2(input_y / latent_y)

        print(scale_factor_x, input_x, latent_x)

        stages = int(round((max(scale_factor_x, scale_factor_y))))

        logger.info("Using %d autoencoder stages", stages)

        upscale = []
        channels = latent_shape[-3]
        dim_x = latent_shape[-2]
        dim_y = latent_shape[-1]
        for stage_num in range(stages):
            out_channels = channels // 2
            stage = nn.Sequential(
                nn.Conv2d(channels, out_channels, 3, padding=(1, 1)),
                nn.BatchNorm2d(out_channels),
                nn.LeakyReLU(2.0),
                nn.Upsample(scale_factor=2.0),
            )

            dim_x *= 2.0
            dim_y *= 2.0
            channels = out_channels

            upscale.append(stage)

        stage = nn.Sequential(
            nn.Conv2d(channels, input_channels, 3, padding=(1, 1)),
            nn.BatchNorm2d(input_channels),
            nn.Upsample(size=(input_x, input_y)),
            nn.Tanh(),
        )
        upscale.append(stage)

        self.layers = nn.Sequential(*upscale)

    def forward(self, x):
        return self.layers(x)


class TimmModel(nn.Module):
    def __init__(
        self,
        name: str,
        input_shape: Tuple[int, int, int],
        pretrained: bool = True,
        decoder: Union[Mapping[str, Any], bool] = True,
        classifier: Union[Mapping[str, Any], bool] = True,
        anomaly_detector: Union[Mapping[str, Any], bool] = True,
        labels: int = 0,
        **kwargs
    ):
        super().__init__()
        self.name = name

        dummy_input = torch.randn(input_shape)

        self.encoder = timm.create_model(
            name, num_classes=0, global_pool="", pretrained=pretrained, **kwargs
        )

        dummy_latent = self.encoder(dummy_input)

        self.decoder = None
        if decoder is True:
            self.decoder = DefaultDecoderHead(dummy_latent.shape, input_shape)
        elif decoder:
            decoder = hydra.utils.instantiate(
                decoder, input_shape=input_shape, latent_shape=dummy_latent.shape
            )

        self.classifier = None
        if labels > 0:
            if classifier is True:
                self.classifier = DefaultClassifierHead(
                    latent_shape=dummy_latent.shape, num_classes=labels
                )
            elif classifier:
                self.classifier = hydra.utils.instantiate(
                    latent_shape=dummy_latent.shape, num_classes=labels
                )

        self.anomaly_detector = None
        if self.anomaly_detector is True:
            self.anomaly_detector = DefaultAnomalyDetector(dummy_latent.shape)
        elif self.anomaly_detector:
            self.anomaly_detector = hydra.utils.instantiate(
                anomaly_detector, latent_shape=dummy_latent.shape
            )

        self.input_shape = input_shape

    def forward(
        self, x: torch.Tensor, decode=True, classify=True, anomaly=True
    ) -> Mapping[str, torch.Tensor]:
        result = {}

        latent = self.encoder(x)
        result["latent"] = latent

        if self.decoder is not None and decode is True:
            decoded = self.decoder(latent)
            result["decoded"] = decoded

        if self.classifier is not None and classify is True:
            pred = self.classifier(latent)
            result["logits"] = pred

        if self.anomaly_predictor is not None and anomaly is True:
            anomaly_score = self.anomaly(latent)
            result["anomaly_score"] = anomaly_score

        return result
