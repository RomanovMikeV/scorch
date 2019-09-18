import numpy

class DataSetWrapper():
    '''
    This is the wrapper for a dataset class.

    This class should have the following methods:
    __init__, __len__, __getitem__.
    '''

    def __init__(self, dataset, name):
        self.dataset = dataset
        self.name = name

        self.order = numpy.arange(len(self.dataset))

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, index):
        real_index = self.order[index]
        dataset_res = self.dataset[real_index]

        return dataset_res, str(self.name) + '_' + str(real_index)

    def shuffle(self):
        self.order = numpy.random.permutation(len(self.dataset))