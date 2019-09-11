import setka
import setka.base
import setka.callbacks

import torch

import torchvision.datasets
import torchvision.transforms

from torch import nn
import torch.nn.functional as F

import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)),  '..'))
import tiny_model
import test_dataset

import matplotlib.pyplot as plt

from test_metrics import tensor_loss as loss
from test_metrics import tensor_acc as acc

ds = test_dataset.CIFAR10()
model = tiny_model.TensorNet()

trainer = setka.base.Trainer(callbacks=[
                                 setka.callbacks.DataSetHandler(ds, batch_size=32, limits=2),
                                 setka.callbacks.ModelHandler(model),
                                 setka.callbacks.LossHandler(loss),
                                 setka.callbacks.OneStepOptimizers(
                                    [
                                        setka.base.OptimizerSwitch(
                                            model.layer1,
                                            torch.optim.SGD,
                                            lr=0.0,
                                            momentum=0.9,
                                            weight_decay=5e-4,
                                            is_active=True),
                                        setka.base.OptimizerSwitch(
                                            model.layer2,
                                            torch.optim.SGD,
                                            lr=0.0,
                                            momentum=0.9,
                                            weight_decay=5e-4,
                                            is_active=False),
                                        setka.base.OptimizerSwitch(
                                            model.layer3,
                                            torch.optim.SGD,
                                            lr=0.0,
                                            momentum=0.9,
                                            weight_decay=5e-4,
                                            is_active=False)
                                    ]
                                 ),
                                 setka.callbacks.ComputeMetrics([loss, acc]),
                                 setka.callbacks.UnfreezeOnPlateau('tensor_acc', max_mode=True),
                                 setka.callbacks.GarbageCollector()
                             ])

for index in range(15):
    trainer.one_epoch('train', 'train')
    trainer.one_epoch('valid', 'train')
    trainer.one_epoch('valid', 'valid')
