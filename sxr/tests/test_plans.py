import logging

import pytest
from bluesky.preprocessors  import run_wrapper
from ophyd.sim import SynAxis

from .conftest import SynSequencer
from ..plans import mcgrain_scan

logger = logging.getLogger(__name__)


def test_mcgrain_scan(fresh_RE):
    m1 = SynAxis(name="m1")
    m2 = SynAxis(name="m2")
    seq = SynSequencer('', name='sequencer')
    
    def test_plan():
        yield from mcgrain_scan(m1, m2, seq, 0, 5, 6, 5)
        assert m1.position == 5.0
        assert m2.position == 30
        assert seq.state_control.get() == 1

    # Send all metadata/data captured to the BestEffortCallback.
    fresh_RE(run_wrapper(test_plan()))
