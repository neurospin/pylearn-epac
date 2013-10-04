# -*- coding: utf-8 -*-
"""
Created on Fri Oct  4 10:18:13 2013

@author: jinpeng.li@cea.fr
"""
import numpy as np
from sklearn import datasets
from epac import Methods


class TOY_CLF:
    def __init__(self, v_lambda):
        self.v_lambda = v_lambda
        self.v_beta = None

    def _get_error(self, v_beta, v_lambda, X, y):
        pred_y = np.dot(X, v_beta)
        ss_error = np.sum((y - pred_y) ** 2, axis=0)
        return ss_error

    def transform(self, X, y):
        len_beta = X.shape[1]

        min_err = 0
        if self.v_beta:
            min_err = self._get_error(self.v_beta, self.v_lambda, X, y)

        # Search the beta which minimizes the error function
        # ==================================================
        for i in xrange(10):
            v_beta = np.random.random(len_beta)
            err = self._get_error(v_beta, self.v_lambda, X, y)
            if (self.v_beta == None) or err < min_err:
                self.v_beta = v_beta
                min_err = err

        pred_y = np.dot(X, v_beta)
        return {"y/pred": pred_y, "y/true": y, "best_beta": self.v_beta}


if __name__ == "__main__":
    ## 1) Build dataset
    ## ================================================
    X, y = datasets.make_classification(n_samples=12,
                                        n_features=10,
                                        n_informative=2,
                                        random_state=1)
    Xy = {"X": X, "y": y}
    methods = Methods(*[TOY_CLF(v_lambda=v_lambda) for v_lambda in [1, 2]])
    print methods.run(**Xy)