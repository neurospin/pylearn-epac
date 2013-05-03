#!/usr/bin/env python

# -*- coding: utf-8 -*-
"""
Created on 2 May 2013

@author: edouard.duchesnay@cea.fr
@author: benoit.da_mota@inria.fr
@author: jinpeng.li@cea.fr

"""

import unittest
import os
import getpass
import sys
import numpy as np
import shutil


def displayres(res_epac):
    
    for k1 in res_epac.keys():
        print ""+k1
        for k2 in res_epac[k1].keys():
            print "  "+k2
            print "    axis_name="+repr(res_epac[k1][k2].axis_name)
            print "    axis_values="+repr(res_epac[k1][k2].axis_values)
            for e3 in list(res_epac[k1][k2]):
                for e4 in list(e3):
                    print "      e4="+repr(e4)

def is_numeric_paranoid(obj):
    
    return isinstance(obj, (int, long, float, complex))

    
def isequal(array1,array2):
    
    if(isinstance(array1,dict)):
      for key in array1.keys():
         if not isequal(array1[key],array2[key]):
             return False
        
      return True
    
    
    array1=np.asarray(list(array1))
    array2=np.asarray(list(array2))
    
    for index in xrange(len(array1.flat)):

        if type(array1.flat[index]) is np.ndarray or type(array1.flat[index]) is list:
            return isequal(array1.flat[index],array2.flat[index])
        else:
            if (is_numeric_paranoid(array1.flat[index])):
                if (np.absolute(array1.flat[index] - 
                array2.flat[index]) > 0.00001 ):
                    return False
            else:
                if array1.flat[index] != array2.flat[index]:
                    return False
    return True

class EpacWorkflowTest(unittest.TestCase):
    
  def setUp(self):
      pass
  
  def tearDown(self): 
      pass
  
  def test_workflow(self):
    
    ########################################################################
    ## Input paths
    '''
    +my_epac_working_directory
      -epac_datasets.npz
      +storekeys
        +...
      -epac_workflow_example
    '''
    
    ## Setup a working directory (my_working_directory)
    my_working_directory="/tmp/my_epac_working_directory"
    
    ## key_file and datasets_file should be ***RELATIVE*** path
    ## It is mandatory for mapping path in soma-workflow
    ## since my_working_directory will be changed on the cluster
    datasets_file = "./epac_datasets.npz"
    key_file="./storekeys"
    soma_workflow_file="./epac_workflow_example"      
    
    #######################################################################
    ## Change the working directory 
    ## so that we can use relative path in the directory my_working_directory
    
    
    
    if os.path.isdir(my_working_directory):
        shutil.rmtree(my_working_directory)
    
    os.mkdir(my_working_directory)
    
    os.chdir(my_working_directory)
      
    ######################################################################
    ## DATASET
    from sklearn import datasets
    from sklearn.svm import SVC
    from sklearn.feature_selection import SelectKBest
    
    
    X, y = datasets.make_classification(n_samples=10, n_features=50,
                                        n_informative=5) 
                                        
    np.savez(datasets_file, X=X, y=y)
    
    
    #######################################################################
    ## EPAC WORKFLOW
    # -------------------------------------
    #             ParPerm                Perm (Splitter)
    #         /     |       \
    #        0      1       2            Samples (Slicer)
    #        |
    #       ParCV                        CV (Splitter)
    #  /       |       \
    # 0        1       2                 Folds (Slicer)
    # |        |       |
    # Seq     Seq     Seq                Sequence
    # |
    # 2                                  SelectKBest (Estimator)
    # |
    # ParGrid
    # |                     \
    # SVM(linear,C=1)   SVM(linear,C=10)  Classifiers (Estimator)
    
    from epac import ParPerm, ParCV, WF, Seq, ParGrid
    
    wf=None
    
    pipeline = Seq(SelectKBest(k=2), 
                   ParGrid(*[SVC(kernel="linear", C=C) for C in [1, 10]]))
                   
    wf = ParPerm(ParCV(pipeline, n_folds=3),
                        n_perms=10, permute="y", y=y)
                        
    
    wf.save(store=key_file)
    
    
    
    
    
    ########################################################################
    ## Nodes to run with soma-workflow
    # nodes = wf.get_node(regexp="*/ParPerm/*")
    ## You can try another level
    nodes = wf.get_node(regexp="*/ParGrid/*")
    
    from soma.workflow.client import Helper
    from epac.exports import export2somaworkflow
    
    (wf_id,controller)=export2somaworkflow(
                        datasets_file, 
                        my_working_directory, 
                        nodes, 
                        soma_workflow_file,
                        True,
                        "",
                        "",
                        "")
    
    
    ## wait the workflow to finish
    Helper.wait_workflow(wf_id,controller)
    ## transfer the output files from the workflow
    Helper.transfer_output_files(wf_id,controller)
    controller.delete_workflow(wf_id)
    
    
    from epac.workflow.base import conf
    from epac import WF
    
    os.chdir(my_working_directory)
    
    ##### wf_key depends on your output in your map process
    wf_key=(
    conf.KEY_PROT_FS+
    conf.KEY_PROT_PATH_SEP+
    key_file+
    os.path.sep+os.walk(key_file).next()[1][0]
    )
    
    swf_wf = WF.load(wf_key)
    
    res_swf=swf_wf.reduce()
    
    displayres(res_swf)
    
    ########################################################################
    ## Run without soma-workflow
    wf.fit_predict(X=X, y=y)
    
    res_epac=wf.reduce()
    
    displayres(res_epac)
    
    
    R1=res_epac
    R2=res_swf
    
    
    comp = dict()
    for key in R1.keys():
        
        r1 = R1[key]
        r2 = R2[key]
        
        comp[key]=True
        
        for k in set(r1.keys()).intersection(set(r2.keys())):
            comp[k]=True
            if not isequal(r1[k],r2[k]):
               comp[k]=False
    
    
    for key in comp.keys():
        self.assertTrue(comp[key])



#return comp
#for key in comp:
#    for subkey in comp[key]:
#        self.assertTrue(comp[key][subkey],
#        u'Diff for key: "%s" and attribute: "%s"' % (key, subkey))
    
if __name__ == '__main__':
    unittest.main()