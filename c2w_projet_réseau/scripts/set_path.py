#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

import sys
import os
from os.path import dirname
 
env_var_name = 'R302_PYTHON_PATH'



default_c2w_path = '~stockrsm/res302'
  
def set_path():
    c2w_path = os.getenv(env_var_name, default_c2w_path)
    local_path = dirname(dirname(dirname(os.path.abspath(__file__))))
    stock_rsm_path = os.path.expanduser(c2w_path)
    
    sys.path.insert(0, local_path)
    sys.path.insert(0, stock_rsm_path)    
    return stock_rsm_path
