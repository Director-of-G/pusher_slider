# package info
__author__ = "Jiang Yongpeng"
__copyright__ = "Copyright 2023, Jiang Yongpeng"

__license__ = "Apache v2.0"
__version__ = "0.0.1"

# ----------------------------------------------------------------
# import from *** folder
# ----------------------------------------------------------------

from dyn_sliding_pack.dyn_sliding_pack import classes4opt as params
from dyn_sliding_pack.dyn_sliding_pack import funcs4opt as funcs
from dyn_sliding_pack.dyn_sliding_pack import dynamic_model as model


def load_config(filename):
    import os
    import yaml
    import pathlib
    path = os.path.join(
        pathlib.Path(__file__).parent.resolve(),
        'config',
        filename
    )
    with open(path, 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)