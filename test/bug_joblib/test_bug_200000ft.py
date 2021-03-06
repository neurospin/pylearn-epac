# -*- coding: utf-8 -*-
"""
Created on Mon Oct  7 16:26:35 2013

@author: laure
"""

from sklearn import datasets

X, y = datasets.make_classification(n_samples=500,
                                    n_features=200000,
                                    n_informative=2,
                                    random_state=1)

Xy = dict(X=X, y=y)
## 2) Building workflow
## =======================================================
print " -> Pt2 : X and y created, building workflow"
from sklearn import svm, cross_validation
#kfold = cross_validation.KFold(n=len(X), n_folds=3)
#svc = svm.SVC(C=1, kernel='linear')
#print [svc.fit(X[train], y[train]).score(X[test], y[test]) for train, test in kfold]
from epac import CV, Methods
cv_svm_local = CV(Methods(*[svm.SVC(kernel="linear"),
                            svm.SVC(kernel="rbf")]),
                  n_folds=3)
print " -> Pt3 : Workflow built, defining local engine"
cv_svm = None
n_proc = 2
# Running on the local machine
from epac import LocalEngine
local_engine = LocalEngine(cv_svm_local, num_processes=n_proc)
print " -> Pt4 : Running"
cv_svm = local_engine.run(**Xy)
print " -> Success with %i procs!" % n_proc
