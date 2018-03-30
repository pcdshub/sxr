import numpy as np
from hutch_python.utils import safe_load
from ophyd.sim import SynAxis


# Test axes that may come in handy
with safe_load('Virtual Motors'):
    virtual_motor_1 = SynAxis(name='Virtual Motor 1')
    virtual_motor_2 = SynAxis(name='Virtual Motor 2')
    virtual_motor_3 = SynAxis(name='Virtual Motor 3')
