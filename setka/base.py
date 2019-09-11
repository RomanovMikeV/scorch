"""
This is the base module of the package. It may also be called the
engine. It contains the core classes that are used in the scripts
such as:

* OptimizerSwitch -- wrapper to facilitate work with optimizers.
* DataSet -- a dataset class that Trainer needs.
* Network -- a network class that Trainer needs.
* Trainer -- class that performs training, validation and prediction.

"""


import numpy
import os
import random
import torch
import torch.utils.data
import copy
import collections
import pickle

class OptimizerSwitch():
    '''
    This class contains optimizer and the module that this
    optimizer should optimize. The OptimizerSwitch tells trainer
    if it should switch the modules to the training mode and back
    to evaluation mode and if it should perform optimization for
    this module's parameters.
    '''

    def __init__(self, train_module, optimizer, is_active=True, **kwargs):
        '''
        Constructs the OptimizerSwitch instance.

        Args:
            train_module (torch.nn.Module):

            optimizer (torch.optim.Optimizer):

            is_active (bool):

            **kwargs:

        Example:
        ```
        OptimizerSwitch(
            net.params(),
            torch.optim.Adam,
            lr=3.0e-4,
            is_active=False)
        ```
        '''

        self.optimizer = optimizer(train_module.parameters(), **kwargs)
        self.module = train_module
        self.active = is_active


class DataSet():
    '''
    Dataset class, where all the information about the dataset is
    collected. It contains all the information about the dataset.
    The dataset may be split into the subsets (that are usually
    referred to as ```train```, ```valid``` and ```test```, but
    you may make much more different modes for your needs).

    The DataSet has the following methods:
        * __init__ -- constructor, where the index collection
            is ususally performed. You need to define it.
            In the original constuctor the ```subset``` is set
            to ```train```.

        * getlen -- function that gets the size of the subset of the dataset.
            This function gets as argument the subset ID (hashable).
            You need to define this function in your class.

        * getitem -- function that retrieves the item form the dataset.
            This function gets as arguments the subset ID (hashable) and the
            ID of the element in the subset (index).
            You need to define this function in your class.


        * getitem -- function that selects

        * __len__ -- function that is called when the ```len()```
            operator is called and returns the volume of the
            current subset. Predefined, you do not need to redefine it.

        * __getitem__ -- function that gets the item of the dataset
            by its index. Predefined, you do not need to redefine it.


    '''

    def __init__(self):
        pass

    def getitem(self, subset, index):
        pass

    def getlen(self, subset):
        pass

    def __getitem__(self, *args):
        args = args[0]
        if type(args) is tuple:
            assert(len(args) <= 2)
            assert(len(args) > 0)

            return self.getitem(args[0], args[1])
        else:
            if not hasattr(self, 'subset'):
                sliced_dataset = copy.copy(self)
                sliced_dataset.subset = args
                return sliced_dataset

            else:
                return self.getitem(self.subset, args)

    def __len__(self):
        assert(hasattr(self, 'subset'))
        return self.getlen(self.subset)


class Trainer():
    '''
    Trainer can train and validate your network. It can also
    predict results.

    It contains the following methods:

    * __init__ -- class constructor, where you specify everything
        that you will need during the training procedure.

    * train_one_epoch -- performs training for one epoch

    * validate_one_epoch -- performs validation for one epoch

    * predict -- predicts results

    * save -- dumps network's and optimizer's states to the file

    * load -- loads network's and optimizer's states from the file

    '''

    @staticmethod
    def setup_environment(seed=0,
                          max_threads=4,
                          deterministic_cuda=False,
                          benchmark_cuda=True):
        numpy.random.seed(seed)
        random.seed(seed)
        torch.manual_seed(seed)

        os.environ["OMP_NUM_THREADS"] = str(max_threads)
        os.environ["OPENBLAS_NUM_THREADS"] = str(max_threads)
        os.environ["MKL_NUM_THREADS"] = str(max_threads)
        os.environ["VECLIB_MAXIMUM_THREADS"] = str(max_threads)
        os.environ["NUMEXPR_NUM_THREADS"] = str(max_threads)

        if torch.cuda.is_available():
            torch.cuda.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)

            torch.backends.cudnn.deterministic = deterministic_cuda
            torch.backends.cudnn.benchmark = benchmark_cuda


    def __init__(self,
                 callbacks=[],
                 seed=0,
                 max_threads=4,
                 deterministic_cuda=False,
                 benchmark_cuda=True,
                 silent=False):
        '''
        Class constructor.

        Args:
            model (base.Network) -- model to train

            optimizers (list of base.OptimizerSwitch) -- optimizer
                to use during training. The optimisers whose
                is_active flag is set to True will be used in the
                optimization procedure (there may be many of them)

            criterion (function) -- criterion (loss) function that
                needs to be optimized

            callbacks (list of callbacks.Callback) -- callbacks
                that extend functionality of the trainer.

            seed (int) -- seed for random number generators to use.

            deterministic_cuda (bool) -- flag that specifies if
                the cuda should behave deterministically
                (takes more time to perform computations)

            silent (bool) -- do not show output


        Args:
            model (base.Network): the model for the socket.

            callbacks (list): List of setka.callbacks to use
                during training.

            seed (int): seed to initialize the random value
                generators. 0 by default.

            deterministic_cuda (bool): whether to use deterministic
                CUDA backend. If True, the computations are slower,
                but deterministic.

            batch_to_metrics (int): how many batches to accumulate before
            metrics computation. Default is 1. If None -- use all batches for
            metrics computation.

            silent (bool): no outputs if True.
        '''
        # self.setup_environment(seed=seed,
        #                        max_threads=max_threads,
        #                        deterministic_cuda=deterministic_cuda,
        #                        benchmark_cuda=benchmark_cuda)

        self._callbacks = callbacks

        for callback in self._callbacks:
            callback.trainer = self

        self.status = collections.OrderedDict()

        self._epoch = 0
        self.status['epoch'] = 0
        self._iteration = 0
        self.status['iteration'] = 0

        self._best_metrics = None

        self._stop_epoch = False
        self.run_callbacks('on_init')


    def run_callbacks(self, stage):
        priorities = []
        for callback in self._callbacks:

            if hasattr(callback, 'priority'):
                if isinstance(callback.priority, dict):
                    if stage in callback.priority:
                        priorities.append(-callback.priority[stage])
                    else:
                        priorities.append(0)
                else:
                    priorities.append(-callback.priority)
            else:
                priorities.append(0)
        priorities = numpy.array(priorities)

        order = priorities.argsort(kind='stable')

        for index in order:
            getattr(self._callbacks[index], stage)()


    def one_epoch(self,
                  mode='valid',
                  subset='valid'):

        '''
        Trains a model for one epoch.

        Args:
            dataset (base.DataSet): dataset instance to train on.

            subset (hashable): identifier of the dataset's subset
                which willbe used for training.

            batch_size (int): batch size to use during training.

            num_workers (int): number of workers to use in
                torch.utils.data.DataLoader.

            max_iterations (int): maximum amount of iterations to
                perform during one epoch. If None -- training
                will be performed until the end of the subset.
        '''

        self.status['mode'] = mode
        self._mode = mode

        self.status['subset'] = subset
        self._subset = subset

        if mode == 'train':
            self.status['epoch'] += 1
            self._epoch += 1

        self._epoch_iteration = 0

        self.run_callbacks('on_epoch_begin')
        for i in range(self._n_iterations):

            if mode == 'train':
                self._iteration += 1
                self.status["iteration"] += 1

            self._epoch_iteration += 1

            self.run_callbacks('on_batch_begin')
            self.run_callbacks('on_batch_run')
            self.run_callbacks("on_batch_end")

            if hasattr(self, "_stop_epoch"):
                if self._stop_epoch:
                    self._stop_epoch = False
                    return

        self.run_callbacks("on_epoch_end")


    def get_optimizers_states(self):
        '''
        Gets the optimizers states.

        Returns:
            list with optimizers states
        '''
        res = []
        for optimizer in self._optimizers:
            res.append(optimizer.optimizer.state_dict())
        return res


    def set_optimizers_states(self, states):
        '''
        Sets the optimizers states.

        Args:
            states: list of states for each of the optimizer.
        '''
        for opt_index in range(len(states)):
            self._optimizers[opt_index].optimizer.load_state_dict(states[opt_index])


    def get_optimizers_flags(self):
        '''
        Gets optimizers active flags.

        Returns:
            list with optimizer active flags.
        '''
        res = []
        for optimizer in self._optimizers:
            res.append(optimizer.active)
        return res


    def set_optimizers_flags(self, flags):
        '''
        Sets optimizers active flags.

        Args:
             flags (list): list with optimizers active flags.
        '''
        for opt_index in range(len(flags)):
            self._optimizers[opt_index].active = flags[opt_index]


    # def save(self, name='./checkpoint'):
    #
    #     '''
    #     Saves trainer to the checkpoint (stored in checkpoints directory).
    #
    #     Args:
    #         name (str): name of the file where the model is saved.
    #     '''
    #
    #     checkpoint = {
    #         "epoch": self._epoch,
    #         "iteration": self._iteration,
    #         "model_state": self._model.module.cpu().state_dict()}
    #
    #     if hasattr(self, '_metrics'):
    #         checkpoint['metrics'] = self._metrics
    #
    #     checkpoint['optimizers_states'] = self.get_optimizers_states()
    #     checkpoint['optimizers_flags'] = self.get_optimizers_flags()
    #
    #     # for opt_index in range(len(self._optimizers)):
    #     #     checkpoint['optimizer_state_' + str(opt_index)] = (
    #     #         self._optimizers[opt_index].optimizer.state_dict())
    #     #     checkpoint['optimizer_switch_' + str(opt_index)] = (
    #     #         self._optimizers[opt_index].active)
    #
    #     torch.save(checkpoint,
    #                name)
    #
    #     if torch.cuda.is_available():
    #         self._model.module.cuda()
    #
    #
    # def load(self, checkpoint_name):
    #     '''
    #     Loads model parameters from the checkpoint.
    #
    #     Args:
    #         checkpoint_name (str): path to the checkpoint
    #             to load.
    #     '''
    #     checkpoint = torch.load(open(checkpoint_name, 'rb'))
    #     print("Model restored from", checkpoint_name)
    #
    #     self._epoch = checkpoint['epoch']
    #     self._iteration = checkpoint['iteration']
    #     self._model.module.load_state_dict(checkpoint["model_state"])
    #     if 'metrics' in checkpoint:
    #         self._metrics = checkpoint['metrics']
    #
    #     self.set_optimizers_flags(checkpoint['optimizers_flags'])
    #     self.set_optimizers_states(checkpoint['optimizers_states'])
    #     # if not new_optimizer:
    #     # for opt_index in range(len(self._optimizers)):
    #     #     try:
    #     #         self._optimizers[opt_index].optimizer.load_state_dict(
    #     #             checkpoint["optimizer_state_" + str(opt_index)])
    #     #         self._optimizers[opt_index].active = checkpoint[
    #     #             "optimizer_switch_" + str(opt_index)]
    #     #     except:
    #     #         print('Failed to load optimizer ' +
    #     #             str(opt_index) + '.')
