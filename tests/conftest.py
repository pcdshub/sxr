import sys
import time
import math
import copy
import random
import logging
import inspect
import asyncio
import threading
from functools import wraps

import pytest
import epics
import numpy as np
import pandas as pd
import epics
from ophyd.signal import Signal
from ophyd.sim import SynSignal, SynAxis
from ophyd.device import Device, Component as Cpt
from ophyd.tests.conftest import using_fake_epics_pv
from bluesky.run_engine import RunEngine
from bluesky.tests.conftest import RE

from ..devices import McgrainPalette as McgPalette

logger = logging.getLogger(__name__)

# Define the requires epics
try:
    import epics
    pv = epics.PV("XCS:USR:MMS:01")
    try:
        val = pv.get()
    except:
        val = None
except:
    val = None
epics_subnet = val is not None
requires_epics = pytest.mark.skipif(not epics_subnet,
                                    reason="Could not connect to sample PV")

#Enable the logging level to be set from the command line
def pytest_addoption(parser):
    parser.addoption("--log", action="store", default="INFO",
                     help="Set the level of the log")
    parser.addoption("--logfile", action="store", default=None,
                     help="Write the log output to specified file path")

#Create a fixture to automatically instantiate logging setup
@pytest.fixture(scope='session', autouse=True)
def set_level(pytestconfig):
    #Read user input logging level
    log_level = getattr(logging, pytestconfig.getoption('--log'), None)

    #Report invalid logging level
    if not isinstance(log_level, int):
        raise ValueError("Invalid log level : {}".format(log_level))

    #Create basic configuration
    logging.basicConfig(level=log_level,
                        filename=pytestconfig.getoption('--logfile'))

@pytest.fixture(scope='function')
def fresh_RE(request):
    return RE(request)

def get_classes_in_module(module, subcls=None, blacklist=None):
    classes = []
    blacklist = blacklist or list()
    all_classes = [cls for _, cls in inspect.getmembers(module) 
                   if cls not in blacklist]
    for cls in all_classes:
        try:
            if cls.__module__ == module.__name__:
                if subcls is not None:
                    try:
                        if not issubclass(cls, subcls):
                            continue
                    except TypeError:
                        continue
                classes.append(cls)
        except AttributeError:
            pass
    return classes

# Create a fake epics device
@using_fake_epics_pv
def fake_device(device, name="TEST"):
    return device(name, name=name)


class SynSequencer(Device):
    """
    Synthetic centroid signal.
    """
    state_control = Cpt(SynSignal, name='state control')


class SynMotor(SynAxis):
    def move(self, value, *args, **kwargs):
        return self.set(value)


class McgrainPalette(McgPalette):
    x_motor = Cpt(SynMotor, name='LJE Sample X')
    y_motor = Cpt(SynMotor, name='LJE Sample Y')
    z_motor = Cpt(SynMotor, name='LJE Sample Z')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for mot in self.motors:
            mot.limits = (-np.inf, np.inf)
