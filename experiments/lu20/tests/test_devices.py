import logging

import pytest
from bluesky.preprocessors  import run_wrapper
from ophyd.sim import SynAxis
from experiments.lu20 import devices


logger = logging.getLogger(__name__)

def test_shutter_connection():
    print(devices.shutter)


def test_motor_connections():
    """
    If these commands succeed, the motors have succesfully connected.
    """
    print(devices.rsxs_sample_x.user_readback.value)
    print(devices.rsxs_sample_y.user_readback.value)
