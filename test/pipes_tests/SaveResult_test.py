import setka
import torch

import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)),  '..'))
import tiny_model
import test_dataset

from test_metrics import list_loss, dict_loss, tensor_loss
from test_metrics import list_acc, dict_acc, tensor_acc

def test_SaveResult_dict():
    ds = test_dataset.CIFAR10()
    model = tiny_model.DictNet()

    trainer = setka.base.Trainer(pipes=[
                                     setka.pipes.DatasetHandler(ds, batch_size=32, limits=2),
                                     setka.pipes.ModelHandler(model),
                                     setka.pipes.LossHandler(dict_loss),
                                     setka.pipes.OneStepOptimizers(
                                        [
                                            setka.base.Optimizer(
                                                model,
                                                torch.optim.SGD,
                                                lr=0.1,
                                                momentum=0.9,
                                                weight_decay=5e-4)
                                        ]
                                     ),
                                     setka.pipes.SaveResult()
                                 ])

    trainer.run_train(1)

def test_SaveResult_list():
    ds = test_dataset.CIFAR10()
    model = tiny_model.ListNet()

    trainer = setka.base.Trainer(pipes=[
        setka.pipes.DatasetHandler(ds, batch_size=32, limits=2),
        setka.pipes.ModelHandler(model),
        setka.pipes.LossHandler(list_loss),
        setka.pipes.OneStepOptimizers(
            [
                setka.base.Optimizer(
                    model,
                    torch.optim.SGD,
                    lr=0.1,
                    momentum=0.9,
                    weight_decay=5e-4)
            ]
        ),
        setka.pipes.SaveResult()
    ])

    trainer.run_train(1)


def test_SaveResult_tensor():
    ds = test_dataset.CIFAR10()
    model = tiny_model.TensorNet()

    def f(input, output):
        return input, output

    trainer = setka.base.Trainer(pipes=[
        setka.pipes.DatasetHandler(ds, batch_size=32, limits=2),
        setka.pipes.ModelHandler(model),
        setka.pipes.LossHandler(tensor_loss),
        setka.pipes.OneStepOptimizers(
            [
                setka.base.Optimizer(
                    model,
                    torch.optim.SGD,
                    lr=0.1,
                    momentum=0.9,
                    weight_decay=5e-4)
            ]
        ),
        setka.pipes.SaveResult(f=f)
    ])

    trainer.run_train(1)
    trainer.run_epoch('test', 'test', n_iterations=2)
