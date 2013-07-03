"""
Estimator is the basic machine-learning building-bloc of the workflow.
It is a user-defined object that should implements 4 methods:


- fit(<keyword arguments>): return self.

- transform(<keyword arguments>): is called only if the estimator is a
  non-leaf node.
  Return an array or a dictionary. In the latter case, the returned dictionary
  is added to the downstream data-flow.

- predict(<keyword arguments>): is called only if the estimator is a leaf node.
  It return an array or a dictionary. In the latter the returned dictionary is
  added to results.

- score(<keyword arguments>): is called only if the estimator is a leaf node.
  It return an scalar or a dictionary. In the latter the returned dictionary is
  added to results.


@author: edouard.duchesnay@cea.fr
@author: benoit.da_mota@inria.fr
"""

## Abreviations
## tr: train
## te: test

import re
import numpy as np
from epac.workflow.base import BaseNode, key_push, key_split
from epac.utils import _func_get_args_names, train_test_merge, train_test_split
from epac.utils import _sub_dict, _as_dict
from epac.map_reduce.results import ResultSet, Result
from epac.stores import StoreMem
from epac.configuration import conf
from epac.map_reduce.reducers import SummaryStat


## ================================= ##
## == Wrapper node for estimators == ##
## ================================= ##

class InternalEstimator(BaseNode):
    """Estimator Wrapper: Automatically connect estimator.fit and 
    estimator.transform to BaseNode.transform.

    Parameters:
        estimator: object that implement fit and transform

        in_args_fit: list of strings
            names of input arguments of the fit method. If missing discover
            discover it automatically.

        in_args_transform: list of strings
            names of input arguments of the tranform method. If missing,
            discover it automatically.
    """
    def __init__(self, estimator, in_args_fit=None, in_args_transform=None):
        if not hasattr(estimator, "fit") or not \
            hasattr(estimator, "transform"):
            raise ValueError("estimator should implement fit and transform")
        super(InternalEstimator, self).__init__()
        self.estimator = estimator
        self.in_args_fit = _func_get_args_names(self.estimator.fit) \
            if in_args_fit is None else in_args_fit
        self.in_args_transform = _func_get_args_names(self.estimator.transform) \
            if in_args_transform is None else in_args_transform

    def transform(self, **Xy):
        if conf.KW_SPLIT_TRAIN_TEST in Xy:
            Xy_train, Xy_test = train_test_split(Xy)
            self.estimator.fit(**_sub_dict(Xy_train, self.in_args_fit))
            # catch args_transform in ds, transform, store output in a dict
            Xy_out_tr = _as_dict(self.estimator.transform(**_sub_dict(Xy_train,
                                                 self.in_args_transform)),
                           keys=self.in_args_transform)
            Xy_out_te = _as_dict(self.estimator.transform(**_sub_dict(Xy_test,
                                                 self.in_args_transform)),
                           keys=self.in_args_transform)
            Xy_out = train_test_merge(Xy_out_tr, Xy_out_te)
        else:
            self.estimator.fit(**_sub_dict(Xy, self.in_args_fit))
            # catch args_transform in ds, transform, store output in a dict
            Xy_out = _as_dict(self.estimator.transform(**_sub_dict(Xy,
                                                 self.in_args_transform)),
                           keys=self.in_args_transform)
        # update ds with transformed values
        Xy.update(Xy_out)
        return Xy

class LeafEstimator(BaseNode):
    """Estimator Wrapper: Automatically connect estimator.fit and 
    estimator.predict to BaseNode.transform.

    Parameters:
        estimator: object that implement fit and transform

        in_args_fit: list of strings
            names of input arguments of the fit method. If missing discover
            discover it automatically.

        in_args_predict: list of strings
            names of input arguments of the predict method. If missing,
            discover it automatically.

        out_args_predict: list of strings
            names of output arguments of the predict method. If missing,
            discover it automatically by self.in_args_fit - in_args_predict.
            If not differences (such with PCA with fit(X) and predict(X))
            use in_args_predict.
    """
    def __init__(self, estimator, in_args_fit=None, in_args_predict=None,
                 out_args_predict=None):
        if not hasattr(estimator, "fit") or not \
            hasattr(estimator, "predict"):
            raise ValueError("estimator should implement fit and predict")
        super(LeafEstimator, self).__init__()
        self.estimator = estimator
        self.in_args_fit = _func_get_args_names(self.estimator.fit) \
            if in_args_fit is None else in_args_fit
        self.in_args_predict = _func_get_args_names(self.estimator.predict) \
            if in_args_predict is None else in_args_predict
        if out_args_predict is None:
            fit_predict_diff = list(set(self.in_args_fit).difference(self.in_args_predict))
            if len(fit_predict_diff) > 0:
                self.out_args_predict = fit_predict_diff
            else:
                self.out_args_predict = self.in_args_predict
        else: 
            self.out_args_predict =  out_args_predict

    """Extimator Wrapper: connect fit + predict to transform"""
    def transform(self, **Xy):
        if conf.KW_SPLIT_TRAIN_TEST in Xy:
            Xy_train, Xy_test = train_test_split(Xy)
            self.estimator.fit(**_sub_dict(Xy_train, self.in_args_fit))
            # catch args_transform in ds, transform, store output in a dict
            Xy_out_tr = _as_dict(self.estimator.predict(**_sub_dict(Xy_train,
                                                 self.in_args_predict)),
                           keys=self.out_args_predict)
            Xy_out_te = _as_dict(self.estimator.predict(**_sub_dict(Xy_test,
                                                 self.in_args_predict)),
                           keys=self.out_args_predict)
            Xy_out = train_test_merge(Xy_out_tr, Xy_out_te)
        else:
            self.estimator.fit(**_sub_dict(Xy, self.in_args_fit))
            # catch args_transform in ds, transform, store output in a dict
            Xy_out = _as_dict(self.estimator.predict(**_sub_dict(Xy,
                                                 self.in_args_predict)),
                           keys=self.out_args_predict)
        return Xy_out

class CVBestSearchRefit(BaseNode):
    """Cross-validation + grid-search then refit with optimals parameters.

    Average results over first axis, then find the arguments that maximize or
    minimise a "score" over other axis.

    Parameters
    ----------

    See CV parameters, plus other parameters:

    score: str
        the score name to be optimized (default "mean_score_te").

    arg_max: boolean
        True/False take parameters that maximize/minimize the score. Default
        is True.
    """

    def __init__(self, node, **kwargs):
        super(CVBestSearchRefit, self).__init__(estimator=None)
        score = kwargs.pop("score") if "score" in kwargs else "mean_score_te"
        arg_max = kwargs.pop("arg_max") if "arg_max" in kwargs else True
        from epac.workflow.splitters import CV
        #methods = Methods(*tasks)
        cv = CV(node=node, reducer=SummaryStat(keep=False), **kwargs)
        self.score = score
        self.arg_max = arg_max
        self.add_child(cv)  # first child is the CV

    def get_signature(self):
        return self.__class__.__name__

    def get_children_top_down(self):
        """Return children during the top-down execution."""
        return []

    def fit(self, recursion=True, **Xy):
        # Fit/predict CV grid search
        cv = self.children[0]
        cv.store = StoreMem()  # local store erased at each fit
        from epac.workflow.splitters import CV
        from epac.workflow.pipeline import Pipe
        if not isinstance(cv, CV):
            raise ValueError('Child of %s is not a "CV."'
            % self.__class__.__name__)
        cv.fit_predict(recursion=True, **Xy)
        #  Pump-up results
        cv_result_set = cv.reduce(store_results=False)
        key_val = [(result.key(), result[self.score]) for result in cv_result_set]
        mean_cv = np.asarray(zip(*key_val)[1])
        mean_cv_opt = np.max(mean_cv) if self.arg_max else  np.min(mean_cv)
        idx_best = np.where(mean_cv == mean_cv_opt)[0][0]
        best_key = key_val[idx_best][0]
        # Find nodes that match the best
        nodes_dict = {n.get_signature(): n for n in self.walk_true_nodes() \
            if n.get_signature() in key_split(best_key)}
        refited = Pipe(*[nodes_dict[k].estimator for k in key_split(best_key)])
        refited.store = StoreMem()    # local store erased at each fit
        self.children = self.children[:1]
        self.add_child(refited)
        refited.fit(recursion=True, **Xy)
        refited_result_set = refited.reduce(store_results=False)
        result_set = ResultSet(refited_result_set)
        result = result_set.values()[0]  # There is only one
        result["key"] = self.get_signature()
        result["best_params"] = [dict(sig) for sig in key_split(best_key, eval=True)]
        self.save_state(result_set, name="result_set")
        #to_refit.bottum_up(store_results=False)
        # Delete (eventual) about previous refit
        return self

    def predict(self, recursion=True, **Xy):
        """Call transform  with sample_set="test" """
        refited = self.children[1]
        pred = refited.predict(recursion=True, **Xy)
        # Update current results with refited prediction
        refited_result = refited.reduce(store_results=False).values()[0]
        result = self.load_state(name="result_set").values()[0]
        result.update(refited_result.payload())
        return pred

    def fit_predict(self, recursion=True, **Xy):
        Xy_train, Xy_test = train_test_split(Xy)
        self.fit(recursion=False, **Xy_train)
        Xy_test = self.predict(recursion=False, **Xy_test)
        return Xy_test

    def reduce(self, store_results=True):
        # Terminaison (leaf) node return result_set
        return self.load_state(name="result_set")
