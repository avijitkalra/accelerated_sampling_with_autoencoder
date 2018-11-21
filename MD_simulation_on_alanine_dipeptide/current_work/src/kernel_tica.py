import numpy as np, pyemma as py
# from msmbuilder.decomposition.tica import tICA
from sklearn.kernel_approximation import Nystroem

"""modified from https://github.com/msmbuilder/msmbuilder/blob/master/msmbuilder/decomposition/ktica.py"""
"""reference: [1] Schwantes, Christian R., and Vijay S. Pande. J. Chem Theory Comput. 11.2 (2015): 600--608."""

class Kernel_tica(object):
    def __init__(self, n_components, lag_time,
                 gamma,             # gamma value for rbf kernel
                 n_components_nystroem=100,  # number of components for Nystroem kernel approximation
                 landmarks = None,
                 shrinkage = None
                 ):
        self._n_components = n_components
        self._lag_time = lag_time
        self._n_components_nystroem = n_components_nystroem
        self._landmarks = landmarks
        self._gamma = gamma
        self._nystroem = Nystroem(gamma=gamma, n_components=n_components_nystroem)
        self._tica = py.coordinates.tica(None, lag=lag_time, dim=n_components, kinetic_map=True)
        # self._tica = tICA(n_components=n_components, lag_time=lag_time, shrinkage=shrinkage)
        self._shrinkage = shrinkage
        return

    def fit(self, sequence_list):
        if self._landmarks is None:
            self._nystroem.fit(np.concatenate(sequence_list))
        else:
            print("using landmarks")
            self._nystroem.fit(self._landmarks)
        sequence_transformed = [self._nystroem.transform(item) for item in sequence_list]
        self._tica.fit(sequence_transformed)
        return

    def transform(self, sequence_list):
        return self._tica.transform(
            [self._nystroem.transform(item) for item in sequence_list])

    def fit_transform(self, sequence_list):
        self.fit(sequence_list)
        return self.transform(sequence_list)

    def score(self, sequence_list):
        model = self.__class__(n_components = self._n_components, lag_time=self._lag_time, gamma=self._gamma,
                               n_components_nystroem=self._n_components_nystroem, landmarks=self._landmarks,
                               shrinkage=self._shrinkage)
        model.fit(sequence_list)
        return np.sum(model._tica.eigenvalues)