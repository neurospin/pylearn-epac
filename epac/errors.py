#!/usr/bin/env python

# -*- coding: utf-8 -*-
"""
Created on 2 May 2013

@author: edouard.duchesnay@cea.fr
@author: benoit.da_mota@inria.fr
@author: jinpeng.li@cea.fr

"""
class NoSomaWFError(Exception):
    """The soma-workflow is not found 
    
    The soma-workflow is not found. Please verify your soma-workflow on 
    your computer.
    
    """
    pass