from enum import Enum
import math
from typing import Dict, Any

import torch
import torch.nn as nn
from torch.autograd import Variable
import torch.nn.functional as F


from ..utils import ConfigType, SerializableModule

class ApproximateGlobalAveragePooling1D(nn.Module):
    def __init__(self, size):
        super().__init__()
        def next_power_of2(x):
            return 1<<(x-1).bit_length()

        self.size = size
        self.divisor = next_power_of2(size)

    def forward(self, x):
        x = torch.sum(x, dim=2, keepdim=True)
        x = x / self.divisor

        return x
        
class TCResidualBlock(nn.Module):
    def __init__(self, input_channels, output_channels, size, stride, dilation, clipping_value,  bottleneck, channel_division, separable):
        super().__init__()
        self.stride = stride
        self.clipping_value = clipping_value
        if stride > 1:
            # No dilation needed: 1x1 kernel
            self.downsample = nn.Sequential(
                nn.Conv1d(input_channels, output_channels, 1, stride, bias=False),
                nn.BatchNorm1d(output_channels),
                nn.Hardtanh(0.0, self.clipping_value))
        
        pad_x = size // 2

        if bottleneck:
            groups = output_channels//channel_division if separable else 1
            self.convs = nn.Sequential(
                nn.Conv1d(input_channels, output_channels//channel_division, 1, stride=1, dilation=dilation, bias=False),
                nn.Conv1d(output_channels//channel_division, output_channels//channel_division, size, stride=stride, padding=dilation*pad_x, dilation=dilation, bias=False, groups=groups),
                nn.Conv1d(output_channels//channel_division, output_channels, 1, stride=1, dilation=dilation, bias=False),
                nn.BatchNorm1d(output_channels),
                nn.Hardtanh(0.0, self.clipping_value),
                nn.Conv1d(output_channels, output_channels//channel_division, 1, stride=1, dilation=dilation, bias=False),
                nn.Conv1d(output_channels//channel_division, output_channels//channel_division, size, 1, padding=dilation*pad_x, dilation=dilation, bias=False, groups=groups),
                nn.Conv1d(output_channels//channel_division, output_channels, 1, stride=1, dilation=dilation, bias=False),
                nn.BatchNorm1d(output_channels))
        else:
            self.convs = nn.Sequential(
                nn.Conv1d(input_channels, output_channels, size, stride, padding=dilation*pad_x, dilation=dilation, bias=False),
                nn.BatchNorm1d(output_channels),
                nn.Hardtanh(0.0, self.clipping_value),
                nn.Conv1d(output_channels, output_channels, size, 1, padding=dilation*pad_x, dilation=dilation, bias=False),
                nn.BatchNorm1d(output_channels))

            
        self.relu = nn.Hardtanh(0.0, self.clipping_value)
            
    def forward(self, x):
        y = self.convs(x)
        if self.stride > 1:
            x = self.downsample(x)
            
        res = self.relu(y + x)
        
        return res
  
class TCResNetModel(SerializableModule):
    def __init__(self, config):
        super().__init__()
        
        n_labels = config["n_labels"]
        width = config["width"]
        height = config["height"]
        dropout_prob = config["dropout_prob"]
        width_multiplier = config["width_multiplier"]
        self.fully_convolutional = config["fully_convolutional"]
        dilation = config["dilation"]        
        clipping_value = config["clipping_value"]
        bottleneck = config["bottleneck"]
        channel_division = config["channel_division"]
        separable = config["separable"]

        self.layers = nn.ModuleList()
  
        input_channels = height
  
        x = Variable(torch.zeros(1, height, width))
  
        count = 1
        while "conv{}_size".format(count) in config:
                output_channels_name = "conv{}_output_channels".format(count)
                size_name = "conv{}_size".format(count)
                stride_name = "conv{}_stride".format(count)
                
                output_channels = int(config[output_channels_name] * width_multiplier)
                size = config[size_name]
                stride = config[stride_name]

                # Change first convolution to bottleneck layer.
                if bottleneck[0] == 1:
                    channel_division_local = channel_division[0]
                    # Change bottleneck layer to sepearable convolution
                    groups =  output_channels//channel_division_local if separable[0] else 1
            
                    conv1 = nn.Conv1d(input_channels, output_channels//channel_division_local, 1, 1, bias = False)
                    conv2 = nn.Conv1d(output_channels//channel_division_local, output_channels//channel_division_local, size, stride, bias = False, groups=groups)
                    conv3 = nn.Conv1d(output_channels//channel_division_local, output_channels, 1, 1, bias = False)
                    self.layers.append(conv1)
                    self.layers.append(conv2)
                    self.layers.append(conv3)
                else:
                    conv = nn.Conv1d(input_channels, output_channels, size, stride, bias = False)
                    self.layers.append(conv)
                
                input_channels = output_channels
                count += 1
                
        count = 1
        while "block{}_conv_size".format(count) in config:
                output_channels_name = "block{}_output_channels".format(count)
                size_name = "block{}_conv_size".format(count)
                stride_name = "block{}_stride".format(count)
                
                output_channels = int(config[output_channels_name] * width_multiplier)
                size = config[size_name]
                stride = config[stride_name] 
                
                # Use same bottleneck, channel_division factor and separable configuration for all blocks
                block = TCResidualBlock(input_channels, output_channels, size, stride, dilation ** count, clipping_value, bottleneck[1], channel_division[1], separable[1])
                self.layers.append(block)
                 
                input_channels = output_channels
                count += 1
        
        for layer in self.layers: 
            x = layer(x)
        
        shape = x.shape
        average_pooling = ApproximateGlobalAveragePooling1D(x.shape[2]) #nn.AvgPool1d((shape[2]))
        self.layers.append(average_pooling)
        
        x = average_pooling(x)

        if not self.fully_convolutional:
            x = x.view(1,-1)
            
        shape = x.shape
        
        self.dropout = nn.Dropout(dropout_prob)

        if self.fully_convolutional:
            self.fc = nn.Conv1d(shape[1], n_labels, 1, bias = False)
        else:
            self.fc = nn.Linear(shape[1], n_labels, bias=False)


    def forward(self, x):
        for layer in self.layers:
            x = layer(x)
        
        x = self.dropout(x)
        if not self.fully_convolutional:
            x = x.view(x.size(0), -1)
        x = self.fc(x)
        
        return x

class ExitWrapperBlock(nn.Module):
    def __init__(self,
                 wrapped_block : nn.Module,
                 exit_branch : nn.Module, 
                 threshold : float,
                 lossweight : float):

        super().__init__()
        
        self.wrapped_block =  wrapped_block
        self.threshold = threshold
        self.lossweight = lossweight
        self.exit_branch = exit_branch
        self.exit_result = torch.Tensor()

    def forward(self, x):
        x = self.wrapped_block.forward(x)

        x_exit = self.exit_branch.forward(x)
        self.exit_result = x_exit
        
        return x
        
class BranchyTCResNetModel(TCResNetModel):
    def __init__(self, config : Dict[str, Any]):
        super().__init__(config)

        dropout_prob = config["dropout_prob"]
        n_labels = config["n_labels"]
        
        self.earlyexit_thresholds = config["earlyexit_thresholds"]
        self.earlyexit_lossweights = config["earlyexit_lossweights"]

        assert len(self.earlyexit_thresholds) == len(self.earlyexit_lossweights)
        assert sum(self.earlyexit_lossweights) < 1.0

        
        
        exit_candidate = TCResidualBlock

        new_layers = nn.ModuleList()

        x = Variable(torch.zeros(1, config["height"], config["width"]))
        
        exit_count = 0
        for layer in self.layers:
            x = layer.forward(x)
            if isinstance(layer, exit_candidate) and exit_count < len(self.earlyexit_thresholds):
                # Simplified exit branch
                exit_branch = nn.Sequential(
                    nn.Conv1d(x.shape[1], n_labels, 1, bias = False),
                    nn.BatchNorm1d(n_labels),
                    nn.ReLU(),
                    ApproximateGlobalAveragePooling1D(x.shape[2]),
                    nn.Dropout(dropout_prob),
                    nn.Conv1d(n_labels, n_labels, 1, bias = False),
                    #nn.BatchNorm1d(n_labels),
                    #nn.ReLU()
                )
                
                exit_wrapper = ExitWrapperBlock(layer,
                                                exit_branch,
                                                self.earlyexit_thresholds[exit_count],
                                                self.earlyexit_lossweights[exit_count])
                
                new_layers.append(exit_wrapper)
                exit_count += 1
            else:
                new_layers.append(layer)

        self.exit_count = exit_count
        self.exits_taken = [0] * (exit_count+1)
        self.layers = new_layers


    def reset_stats(self):
        self.exits_taken = [0] * (self.exit_count+1)

    def print_stats(self):
        for num, taken in enumerate(self.exits_taken):
            print("Exit {} taken: {}".format(num, taken))

    def forward(self, x):
        x = super().forward(x)

        if self.training:
            results = []
            for layer in self.layers:
                if isinstance(layer, ExitWrapperBlock):
                    results.append(layer.exit_result)
             
            results.append(x)
        
            return results

        #Forward in eval mode returns only first exit with estimated loss < thresholds
        exit_number = 0
    
        zeros = torch.zeros(x.shape, device=x.device)
        ones = torch.ones(x.shape, device=x.device)
        
        current_mask = torch.ones(x.shape, device=x.device)
        global_result = torch.zeros(x.shape, device=x.device)

        batch_taken = [0] * (self.exit_count)
        
        for layer in self.layers:
            if isinstance(layer, ExitWrapperBlock):
                threshold = layer.threshold
                result = layer.exit_result
                result = result.view(global_result.shape)
                estimated_labels = result.argmax(dim=1)
                thresholded_result = torch.clamp(result, -1.0, 0.9925)
                #print(result)

                # Cross Entropy Loss function
                #estimated_losses = torch.nn.functional.cross_entropy(thresholded_result, estimated_labels, reduce=False)
                #print(exit_number, "True losses:", estimated_losses)

                # Approximated Entropy Loss
                
                #print(thresholded_result)
                expected_result = torch.zeros(thresholded_result.shape, device=x.device)
                for row, column in enumerate(estimated_labels):
                    for column2 in range(expected_result.shape[1]):
                        expected_result[row, column2] = thresholded_result[row, column]

                #print(estimated_labels)
                #print(expected_result)
                diff = thresholded_result-expected_result
                #estimated_losses = torch.sum(1 + diff + torch.pow(diff, 2)/2 + torch.pow(diff, 3)/6 + torch.pow(diff, 4)/24+torch.pow(diff, 5)/120, dim=1) 

                estimated_losses = torch.sum(1 + diff + torch.pow(diff, 2)/2 + torch.pow(diff, 3)/8, dim=1)
                #estimated_losses_3 = torch.sum(1 + diff + torch.pow(diff, 2)/2 + torch.pow(diff, 3)/6, dim=1)

                
                #print(exit_number, "Estimated losses:", -torch.log(estimated_losses**(-1)))
                #print(exit_number, "Estimated losses:", -torch.log(estimated_losses_3**(-1)))
                threshold = math.exp(threshold)
                
                batch_taken[exit_number] = torch.sum(estimated_losses < threshold).item()
                estimated_losses = estimated_losses.reshape(-1, 1).expand(global_result.shape)
                
                
                masked_result = torch.where(estimated_losses < threshold, result, zeros)
                masked_result = torch.where(current_mask > 0, masked_result, zeros)
                current_mask = torch.where(estimated_losses < threshold, zeros, current_mask)
                
                #print("result:", result)
                #print("Masked result:", masked_result)
                #print("x:", x)
                
                global_result += masked_result

                #print("global_result:", global_result)

                exit_number += 1

        global_result += torch.where(current_mask > 0, x, global_result)
        batch_taken.append(x.shape[0]-sum(batch_taken))
        print("Batch taken: ", batch_taken)
        
        return global_result
                

    def get_loss_function(self):
        multipliers = list(self.earlyexit_lossweights)
        multipliers.append(1.0 - sum(multipliers))
        criterion = nn.CrossEntropyLoss()
        def loss_function(scores, labels):
            if isinstance(scores, list):
                loss = torch.zeros([1], device=scores[0].device)
                for multiplier, current_scores in zip(multipliers, scores):
                    current_scores = current_scores.view(current_scores.size(0), -1)
                    current_loss = multiplier * criterion(current_scores, labels)
                    loss += current_loss
                return loss
            else:
                scores = scores.view(scores.size(0), -1)
                return criterion(scores, labels)
            
        return loss_function

        
configs= {
    ConfigType.TC_RES_2.value: dict(
        features="mel",
        fully_convolutional=False,
        dropout_prob = 0.5,
        width_multiplier = 1.0,
        dilation = 1,
        clipping_value = 100000,
        bottleneck = (0,0),
        channel_division = (2,4),
        separable = (0,0),
        conv1_size = 3,
        conv1_stride = 1,
        conv1_output_channels = 16, 
    ),
    ConfigType.TC_RES_4.value: dict(
        features="mel",
        fully_convolutional=False,
        dropout_prob = 0.5,
        width_multiplier = 1.0,
        dilation = 1,
        clipping_value = 100000,
        bottleneck = (0,0),
        channel_division = (2,4),
        separable = (0,0),
        conv1_size = 3,
        conv1_stride = 1,
        conv1_output_channels = 16,
        block1_conv_size = 9,
        block1_stride = 2,
        block1_output_channels = 24, 
    ),
    ConfigType.TC_RES_6.value: dict(
        features="mel",
        fully_convolutional=False,
        dropout_prob = 0.5,
        width_multiplier = 1.0,
        dilation = 1,
        clipping_value = 100000,
        bottleneck = (0,0),
        channel_division = (2,4),
        separable = (0,0),
        conv1_size = 3,
        conv1_stride = 1,
        conv1_output_channels = 16,
        block1_conv_size = 9,
        block1_stride = 2,
        block1_output_channels = 24,
        block2_conv_size = 9,
        block2_stride = 2,
        block2_output_channels = 32,
    ),
    ConfigType.TC_RES_8.value: dict(
        features="mel",
        fully_convolutional=False,
        dropout_prob = 0.5,
        width_multiplier = 1.0,
        dilation = 1,
        clipping_value = 100000,
        bottleneck = (0,0),
        channel_division = (2,4),
        separable = (0,0),
        conv1_size = 3,
        conv1_stride = 1,
        conv1_output_channels = 16,
        block1_conv_size = 9,
        block1_stride = 2,
        block1_output_channels = 24,
        block2_conv_size = 9,
        block2_stride = 2,
        block2_output_channels = 32,
        block3_conv_size = 9,
        block3_stride = 2,
        block3_output_channels = 48 
    ),
    ConfigType.TC_RES_10.value: dict(
        features="mel",
        fully_convolutional=False,
        dropout_prob = 0.5,
        width_multiplier = 1.0,
        dilation = 1,
        clipping_value = 100000,
        bottleneck = (0,0),
        channel_division = (2,4),
        separable = (0,0),
        conv1_size = 3,
        conv1_stride = 1,
        conv1_output_channels = 16,
        block1_conv_size = 9,
        block1_stride = 2,
        block1_output_channels = 24,
        block2_conv_size = 9,
        block2_stride = 2,
        block2_output_channels = 32,
        block3_conv_size = 9,
        block3_stride = 2,
        block3_output_channels = 48,
        block4_conv_size = 9,
        block4_stride = 2,
        block4_output_channels = 64 
    ),
    ConfigType.TC_RES_12.value: dict(
        features="mel",
        dropout_prob = 0.5,
        fully_convolutional=False,
        width_multiplier = 1.0,
        dilation = 1,
        clipping_value = 100000,
        bottleneck = (0,0),
        channel_division = (4,2),
        separable = (0,0),
        conv1_size = 3,
        conv1_stride = 1,
        conv1_output_channels = 16,
        block1_conv_size = 9,
        block1_stride = 2,
        block1_output_channels = 24,
        block2_conv_size = 9,
        block2_stride = 1,
        block2_output_channels = 24,
        block3_conv_size = 9,
        block3_stride = 2,
        block3_output_channels = 32,
        block4_conv_size = 9,
        block4_stride = 1,
        block4_output_channels = 32,
        block5_conv_size = 9,
        block5_stride = 2,
        block5_output_channels = 48, 
    ),
    ConfigType.TC_RES_14.value: dict(
        features="mel",
        dropout_prob = 0.5,
        fully_convolutional=False,
        width_multiplier = 1.0,
        dilation = 1,
        clipping_value = 100000,
        bottleneck = (0,0),
        channel_division = (4,2),
        separable = (0,0),
        conv1_size = 3,
        conv1_stride = 1,
        conv1_output_channels = 16,
        block1_conv_size = 9,
        block1_stride = 2,
        block1_output_channels = 24,
        block2_conv_size = 9,
        block2_stride = 1,
        block2_output_channels = 24,
        block3_conv_size = 9,
        block3_stride = 2,
        block3_output_channels = 32,
        block4_conv_size = 9,
        block4_stride = 1,
        block4_output_channels = 32,
        block5_conv_size = 9,
        block5_stride = 2,
        block5_output_channels = 48,
        block6_conv_size = 9,
        block6_stride = 1,
        block6_output_channels = 48 
    ),
    ConfigType.TC_RES_16.value: dict(
        features="mel",
        dropout_prob = 0.5,
        fully_convolutional=False,
        width_multiplier = 1.0,
        dilation = 1,
        clipping_value = 100000,
        bottleneck = (0,0),
        channel_division = (4,2),
        separable = (0,0),
        conv1_size = 3,
        conv1_stride = 1,
        conv1_output_channels = 16,
        block1_conv_size = 9,
        block1_stride = 2,
        block1_output_channels = 24,
        block2_conv_size = 9,
        block2_stride = 1,
        block2_output_channels = 24,
        block3_conv_size = 9,
        block3_stride = 2,
        block3_output_channels = 32,
        block4_conv_size = 9,
        block4_stride = 1,
        block4_output_channels = 32,
        block5_conv_size = 9,
        block5_stride = 2,
        block5_output_channels = 48,
        block6_conv_size = 9,
        block6_stride = 1,
        block6_output_channels = 48,
        block7_conv_size = 9,
        block7_stride = 2,
        block7_output_channels = 64 
    ),
    ConfigType.TC_RES_18.value: dict(
        features="mel",
        dropout_prob = 0.5,
        fully_convolutional=False,
        width_multiplier = 1.0,
        dilation = 1,
        clipping_value = 100000,
        bottleneck = (0,0),
        channel_division = (4,2),
        separable = (0,0),
        conv1_size = 3,
        conv1_stride = 1,
        conv1_output_channels = 16,
        block1_conv_size = 9,
        block1_stride = 2,
        block1_output_channels = 24,
        block2_conv_size = 9,
        block2_stride = 1,
        block2_output_channels = 24,
        block3_conv_size = 9,
        block3_stride = 2,
        block3_output_channels = 32,
        block4_conv_size = 9,
        block4_stride = 1,
        block4_output_channels = 32,
        block5_conv_size = 9,
        block5_stride = 2,
        block5_output_channels = 48,
        block6_conv_size = 9,
        block6_stride = 1,
        block6_output_channels = 48,
        block7_conv_size = 9,
        block7_stride = 2,
        block7_output_channels = 64,
        block8_conv_size = 9,
        block8_stride = 1,
        block8_output_channels = 64 
    ),
    
    ConfigType.TC_RES_20.value: dict(
        features="mel",
        dropout_prob = 0.5,
        fully_convolutional=False,
        width_multiplier = 1.0,
        dilation = 1,
        clipping_value = 100000,
        bottleneck = (0,0),
        channel_division = (4,2),
        separable = (0,0),
        conv1_size = 3,
        conv1_stride = 1,
        conv1_output_channels = 16,
        block1_conv_size = 9,
        block1_stride = 2,
        block1_output_channels = 24,
        block2_conv_size = 9,
        block2_stride = 1,
        block2_output_channels = 24,
        block3_conv_size = 9,
        block3_stride = 2,
        block3_output_channels = 32,
        block4_conv_size = 9,
        block4_stride = 1,
        block4_output_channels = 32,
        block5_conv_size = 9,
        block5_stride = 2,
        block5_output_channels = 48,
        block6_conv_size = 9,
        block6_stride = 1,
        block6_output_channels = 48,
        block7_conv_size = 9,
        block7_stride = 2,
        block7_output_channels = 64,
        block8_conv_size = 9,
        block8_stride = 1,
        block8_output_channels = 64,
        block9_conv_size = 9,
        block9_stride = 2,
        block9_output_channels = 80 
    ),
    ConfigType.TC_RES_8_15.value: dict(
        features="mel",
        dropout_prob = 0.5,
        fully_convolutional=False,
        width_multiplier = 1.5,
        dilation = 1,
        clipping_value = 100000,
        bottleneck = (0,0),
        channel_division = (4,2),
        separable = (0,0),
        conv1_size = 3,
        conv1_stride = 1,
        conv1_output_channels = 16,
        block1_conv_size = 9,
        block1_stride = 2,
        block1_output_channels = 24,
        block2_conv_size = 9,
        block2_stride = 2,
        block2_output_channels = 32,
        block3_conv_size = 9,
        block3_stride = 2,
        block3_output_channels = 48 
    ),
    ConfigType.TC_RES_14_15.value: dict(
        features="mel",
        dropout_prob = 0.5,
        fully_convolutional=False,
        width_multiplier = 1.5,
        dilation = 1,
        clipping_value = 100000,
        bottleneck = (0,0),
        channel_division = (4,2),
        separable = (0,0),
        conv1_size = 3,
        conv1_stride = 1,
        conv1_output_channels = 16,
        block1_conv_size = 9,
        block1_stride = 2,
        block1_output_channels = 24,
        block2_conv_size = 9,
        block2_stride = 1,
        block2_output_channels = 24,
        block3_conv_size = 9,
        block3_stride = 2,
        block3_output_channels = 32,
        block4_conv_size = 9,
        block4_stride = 1,
        block4_output_channels = 32,
        block5_conv_size = 9,
        block5_stride = 2,
        block5_output_channels = 48,
        block6_conv_size = 9,
        block6_stride = 1,
        block6_output_channels = 48 
    ),
    ConfigType.BRANCHY_TC_RES_8.value: dict(
        features="mel",
        dropout_prob = 0.5,
        earlyexit_thresholds = [1.2, 1.2],
        earlyexit_lossweights = [0.3, 0.3],
        fully_convolutional=False,
        width_multiplier = 1.5,
        dilation = 1,
        clipping_value = 100000,
        bottleneck = (0,0),
        channel_division = (4,2),
        separable = (0,0),
        conv1_size = 3,
        conv1_stride = 1,
        conv1_output_channels = 16,
        block1_conv_size = 9,
        block1_stride = 2,
        block1_output_channels = 24,
        block2_conv_size = 9,
        block2_stride = 2,
        block2_output_channels = 32,
        block3_conv_size = 9,
        block3_stride = 2,
        block3_output_channels = 48 
    ),
}
