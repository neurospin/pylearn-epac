# -*- coding: utf-8 -*-
"""
Created on Thu Mar 14 14:54:35 2013

Stores for EPAC

@author: edouard.duchesnay@cea.fr
"""

import os
import shutil
# import pickle
import dill as pickle
import joblib
import json
import inspect
import numpy as np
from abc import abstractmethod
from epac.configuration import conf


class TagObject:
    def __init__(self):
        self.hash_id = os.urandom(32)


def func_is_big_nparray(obj):
    if isinstance(obj, np.ndarray):
        num = 1
        for ishape in obj.shape:
            num = num * ishape
        if num > conf.MEMM_THRESHOLD:
            return True
    return False


def func_can_deeper(obj):
    return not isinstance(obj, np.ndarray)


def replace_values(obj, extracted_values, max_depth=10):
    """
    See example in extract_values
    """
    max_depth = max_depth - 1
    if max_depth < 0:
        return obj
    public_props = (name for name in dir(obj)
          if not name.startswith('_') and not callable(getattr(obj, name)))
    for props in public_props:
        if isinstance(getattr(obj, props), TagObject):
            tag_value = getattr(obj, props)
            set_value = extracted_values[tag_value.hash_id]
            setattr(obj, props, set_value)
        else:
            obj2set = replace_values(getattr(obj, props),
                                     extracted_values,
                                     max_depth)
            setattr(obj, props, obj2set)
    return obj


def extract_values(obj,
                   func_is_need_extract,
                   func_can_deeper=None,
                   max_depth=10):
    """
    Example
    -------
    >>> from epac.stores import extract_values
    >>> from epac.stores import replace_values
    >>> from epac.stores import TagObject
    >>>
    >>>
    >>> def func_is_need_extract(obj):
    ...     if type(obj) is str:
    ...         if(len(obj) >= 3):
    ...             return True
    ...     return False
    ...
    >>>
    >>>
    >>> def func_can_deeper(obj):
    ...     return type(obj) is not str
    ...
    >>>
    >>>
    >>> class TestC:
    ...     def __init__(self):
    ...         self.A = "C1A"
    ...         self.B = "C2"
    ...
    >>>
    >>>
    >>> class TestD:
    ...     def __init__(self):
    ...         self.A = "D1"
    ...         self.B = "D2"
    ...         self.C = TestC()
    ...
    >>>
    >>>
    >>> obj = TestD()
    >>> extracted_values, obj = extract_values(obj,
    ...                                        func_is_need_extract,
    ...                                        func_can_deeper)
    >>> print obj.A
    D1
    >>> print obj.B
    D2
    >>> print isinstance(obj.C.A, TagObject)
    True
    >>> print obj.C.B
    C2
    >>> obj = replace_values(obj, extracted_values)
    >>> print obj.A
    D1
    >>> print obj.B
    D2
    >>> print obj.C.A
    C1A
    >>> print obj.C.B
    C2
    """
    replaced_array = {}
    # When obj is replace-able
    if func_is_need_extract(obj):
        replaced_object = TagObject()
        tag_value = obj
        obj = replaced_object
        replaced_array[replaced_object.hash_id] = tag_value
        return (replaced_array, obj)

    max_depth = max_depth - 1
    if max_depth < 0:
        return (replaced_array, obj)
    public_props = (name for name in dir(obj)
          if not name.startswith('_') and not callable(getattr(obj, name)))
    for props in public_props:
        if func_is_need_extract(getattr(obj, props)):
            replaced_object = TagObject()
            tag_value = getattr(obj, props)
            setattr(obj, props, replaced_object)
            replaced_array[replaced_object.hash_id] = tag_value
        else:
            can_deeper = False
            if func_can_deeper is None:
                can_deeper = True
            elif func_can_deeper(obj):
                can_deeper = True

            if can_deeper:
                pros_replaced_array, obj2set = \
                    extract_values(getattr(obj, props),
                                   func_is_need_extract,
                                   func_can_deeper,
                                   max_depth)
                setattr(obj, props, obj2set)
                replaced_array.update(pros_replaced_array)

    return (replaced_array, obj)


class epac_joblib:
    """
    It is optimized for dictionary dump and load
    Since joblib produces too many small files for mamory mapping,
    we try to limit the produced files for dictionary.

    Example
    -------
    import numpy as np
    from epac.stores import epac_joblib

    npdata1 = np.random.random(size=(5,5))
    npdata2 = np.random.random(size=(5,5))

    dict_data = {"1": npdata1, "2": npdata2}
    epac_joblib.dump(dict_data, "/tmp/123")
    dict_data = epac_joblib.load("/tmp/123", "r")

    """
    @staticmethod
    def _epac_is_need_memm(obj):
        if type(obj) is np.ndarray:
            num_float = 1
            for ishape in obj.shape:
                num_float = num_float * ishape
            # equal to 100 * 1024 * 1024 which means 100 MB
            if num_float * 8 > 104857600:
                return True
        return False

    @staticmethod
    def _pickle_dump(obj, filename):
        output = open(filename, 'w+')
        pickle.dump(obj, output)
        output.close()

    @staticmethod
    def _pickle_load(filename):
        infile = open(filename, 'rb')
        obj = pickle.load(infile)
        infile.close()
        return obj

    @staticmethod
    def dump(obj, filename):
        filename_memobj = filename + "_memobj.enpy"
        filename_norobj = filename + "_norobj.enpy"
        mem_obj, normal_obj = extract_values(obj,
                                             func_is_big_nparray,
                                             func_can_deeper)
        joblib.dump(mem_obj, filename_memobj)
        epac_joblib._pickle_dump(normal_obj, filename_norobj)

        outfile = open(filename, "w+")
        outfile.write(filename_memobj)
        outfile.write("\n")
        outfile.write(filename_norobj)
        outfile.write("\n")
        outfile.close()

    @staticmethod
    def load(filename, mmap_mode=None):
        filename_memobj = None
        filename_norobj = None
        mem_obj = None
        normal_obj = None
        # Read index file
        infile = open(filename, "rb")
        lines = infile.readlines()
        infile.close()
        for i in xrange(len(lines)):
            lines[i] = lines[i].strip("\n")
        filename_memobj = lines[0]
        filename_norobj = lines[1]
        # Load Memory obj and Normal obj
        mem_obj = joblib.load(filename_memobj, mmap_mode)
        normal_obj = epac_joblib._pickle_load(filename_norobj)
        # Replace mem_obj (extracted values)
        normal_obj = replace_values(normal_obj, mem_obj)
        return normal_obj


class Store(object):
    """Abstract Store"""

    @abstractmethod
    def save(self, key, obj, merge=False):
        """Store abstract method"""

    @abstractmethod
    def load(self, key):
        """Store abstract method"""


class StoreMem(Store):
    """ Store based on memory"""

    def __init__(self):
        self.dict = dict()

    def save(self, key, obj, merge=False):
        if not merge or not (key in self.dict):
            self.dict[key] = obj
        else:
            v = self.dict[key]
            if isinstance(v, dict):
                v.update(obj)
            elif isinstance(v, list):
                v.append(obj)

    def load(self, key):
        try:
            return self.dict[key]
        except KeyError:
            return None


class StoreFs(Store):
    """ Store based of file system

    Parameters
    ----------
    dirpath: str
        Root directory within file system

    clear: boolean
        If True clear (delete) everything under the root directory.

    """

    def __init__(self, dirpath, clear=False):

        self.dirpath = dirpath
        if clear:
            shutil.rmtree(self.dirpath)
        if not os.path.isdir(self.dirpath):
            os.mkdir(self.dirpath)

    def save(self, key, obj, protocol="txt", merge=False):
        """ Save object

        Parameters
        ----------

        key: str
            The primary key

        obj:
            object to be saved

        protocol: str
            "txt": try with JSON if fail use "bin": (pickle)
        """
        #path = self.key2path(key)
        path = os.path.join(self.dirpath, key)
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        # JSON
        from epac.configuration import conf
        if protocol is "txt":
            file_path = path + conf.STORE_FS_JSON_SUFFIX
            json_failed = self.save_json(file_path, obj)
        if protocol is "bin" or json_failed:
            # saving in json failed => pickle
            file_path = path + conf.STORE_FS_PICKLE_SUFFIX
            self.save_pickle(file_path, obj)

    def load(self, key=""):
        """Load everything that is prefixed with key.

        Parmaters
        ---------
        key: str
            if key point to a file (without the extension), return the file
            if key point to a directory, return a dictionary where
            values are objects corresponding to all files found in all
            sub-directories. Values are indexed with their keys.
            if key is an empty string, assume dirpath is a tree root.

        See Also
        --------
        BaseNode.save()
        """
        from epac.configuration import conf
        from epac.workflow.base import key_pop
        path = os.path.join(self.dirpath, key)
        # prefix = os.path.join(path, conf.STORE_FS_NODE_PREFIX)
        if os.path.isfile(path + conf.STORE_FS_PICKLE_SUFFIX):
            loaded_node = self.load_pickle(path + conf.STORE_FS_PICKLE_SUFFIX)
            return loaded_node
        if os.path.isfile(path + conf.STORE_FS_JSON_SUFFIX):
            loaded_node = self.load_pickle(path + conf.STORE_FS_JSON_SUFFIX)
            return loaded_node
        if os.path.isdir(path):
            filepaths = []
            for base, dirs, files in os.walk(self.dirpath):
                #print base, dirs, files
                for filepath in [os.path.join(base, basename) for
                                 basename in files]:
                    _, ext = os.path.splitext(filepath)
                    if not ext == ".npy" and not ext == ".enpy":
                        filepaths.append(filepath)
            loaded = dict()
            dirpath = os.path.join(self.dirpath, "")
            for filepath in filepaths:
                _, ext = os.path.splitext(filepath)
                if ext == conf.STORE_FS_JSON_SUFFIX:
                    key1 = filepath.replace(dirpath, "").\
                        replace(conf.STORE_FS_JSON_SUFFIX, "")
                    obj = self.load_json(filepath)
                    loaded[key1] = obj
                elif ext == conf.STORE_FS_PICKLE_SUFFIX:
                    key1 = filepath.replace(dirpath, "").\
                        replace(conf.STORE_FS_PICKLE_SUFFIX, "")
                    loaded[key1] = self.load_pickle(filepath)
                elif ext == ".npy" or ext == ".enpy":
                    # joblib files
                    pass
                else:
                    raise IOError('File %s has an unkown extension: %s' %
                                  (filepath, ext))
            if key == "":  # No key provided assume a whole tree to load
                tree = loaded.pop(conf.STORE_EXECUTION_TREE_PREFIX)
                for key1 in loaded:
                    key, attrname = key_pop(key1)
                    #attrname, ext = os.path.splitext(basename)
                    if attrname != conf.STORE_STORE_PREFIX:
                        raise ValueError('Do not know what to do with %s') \
                            % key1
                    node = tree.get_node(key)
                    if not node.store:
                        node.store = loaded[key1]
                    else:
                        keys_local = node.store.dict.keys()
                        keys_disk = loaded[key1].dict.keys()
                        if set(keys_local).intersection(set(keys_disk)):
                            raise KeyError("Merge store with same keys")
                        node.store.dict.update(loaded[key1].dict)
                loaded = tree
            return loaded

    def save_pickle(self, file_path, obj):
        epac_joblib.dump(obj, file_path)
#        output = open(file_path, 'wb')
#        pickle.dump(obj, output)
#        output.close()

    def load_pickle(self, file_path):
#        u'/tmp/store/KFold-0/SVC/__node__NodeEstimator.pkl'
#        inputf = open(file_path, 'rb')
#        obj = pickle.load(inputf)
#        inputf.close()
        from epac.utils import try_fun_num_trials
        kwarg = {"filename": file_path}
        obj = try_fun_num_trials(epac_joblib.load,
                                 ntrials=10,
                                 **kwarg)
        # obj = joblib.load(filename=file_path)
        return obj

    def save_json(self, file_path,  obj):
        obj_dict = obj_to_dict(obj)
        output = open(file_path, 'wb')
        try:
            json.dump(obj_dict, output)
        except TypeError:  # save in pickle
            output.close()
            os.remove(file_path)
            return 1
        output.close()
        return 0

    def load_json(self, file_path):
        inputf = open(file_path, 'rb')
        obj_dict = json.load(inputf)
        inputf.close()
        return dict_to_obj(obj_dict)


## ============================== ##
## == Conversion Object / dict == ##
## ============================== ##

# Convert object to dict and dict to object for Json Persistance
def obj_to_dict(obj):
    # Composite objects (object, dict, list): recursive call
    if hasattr(obj, "__dict__") and hasattr(obj, "__class__")\
        and hasattr(obj, "__module__") and not inspect.isfunction(obj):  # object: rec call
        obj_dict = {k: obj_to_dict(obj.__dict__[k]) for k in obj.__dict__}
        obj_dict["__class_name__"] = obj.__class__.__name__
        obj_dict["__class_module__"] = obj.__module__
        return obj_dict
    elif inspect.isfunction(obj):                     # function
        obj_dict = {"__func_name__": obj.func_name,
                    "__class_module__": obj.__module__}
        return obj_dict
    elif isinstance(obj, dict):                       # dict: rec call
        return {k: obj_to_dict(obj[k]) for k in obj}
    elif isinstance(obj, (list, tuple)):              # list: rec call
        return [obj_to_dict(item) for item in obj]
    elif isinstance(obj, np.ndarray):                 # array: to list
        return {"__array__": obj.tolist()}
    else:
        return obj


def dict_to_obj(obj_dict):
    if isinstance(obj_dict, dict) and '__class_name__' in obj_dict:  # object
        cls_name = obj_dict.pop('__class_name__')               # : rec call
        cls_module = obj_dict.pop('__class_module__')
        obj_dict = {k: dict_to_obj(obj_dict[k]) for k in obj_dict}
        mod = __import__(cls_module, fromlist=[cls_name])
        obj = object.__new__(eval("mod." + cls_name))
        obj.__dict__.update(obj_dict)
        return obj
    if isinstance(obj_dict, dict) and '__func_name__' in obj_dict:  # function
        func_name = obj_dict.pop('__func_name__')
        func_module = obj_dict.pop('__class_module__')
        mod = __import__(func_module, fromlist=[func_name])
        func = eval("mod." + func_name)
        return func
    if isinstance(obj_dict, dict) and '__array__' in obj_dict:
        return np.asarray(obj_dict.pop('__array__'))
    elif isinstance(obj_dict, dict):                         # dict: rec call
        return {k: dict_to_obj(obj_dict[k]) for k in obj_dict}
    elif isinstance(obj_dict, (list, tuple)):                # list: rec call
        return [dict_to_obj(item) for item in obj_dict]
#    elif isinstance(obj, np.ndarray):                       # array: to list
#        return obj.tolist()
    else:
        return obj_dict
