import logging

import numpy as np
import pytest
from ophyd.tests.conftest import using_fake_epics_pv

from .conftest import McgrainPalette

logger = logging.getLogger(__name__)


def test_McgrainPalette_move_method():
    pal = McgrainPalette(name='Test Palette')

    pal.accept_calibration(pal.N, pal.M, np.array([0,0,0]), 
                           np.array([pal.N,0,0]), np.array([0,pal.M,0]))

    pal.move(24)
    assert pal.position == (23.0, 1.0, 0.0)

    pal.move(10, 10)
    assert pal.position == (10.0, 10.0, 0.0)

    pal.move(1, 1, 1)
    assert pal.position == (1.0, 1.0, 1.0)
