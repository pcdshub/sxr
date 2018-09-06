import logging

from bluesky import RunEngine
from bluesky.preprocessors import run_wrapper

from experiments.lu20.devices import (shutter, rsxs_sample_x, rsxs_sample_y,
    tst_23)
from experiments.lu20.plans import rel_smooth_sweep_test, rel_smooth_sweep
from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky.utils import ProgressBarManager

logger = logging.getLogger(__name__)

def macro_sweep_test(target):
    RE = RunEngine({})
    bec = BestEffortCallback()
    RE.subscribe(bec)
    RE.waiting_hook = ProgressBarManager()
    RE(run_wrapper(rel_smooth_sweep_test(tst_23,target)))

def macro_RSXS_smooth_sweep(stroke_height, stroke_spacing, n_strokes,
            both_directions):
    RE = RunEngine({})
    bec = BestEffortCallback()
    RE.subscribe(bec)
    RE.waiting_hook = ProgressBarManager()
    RE(run_wrapper(rel_smooth_sweep(
        mot_x=rsxs_sample_x,
        mot_y=rsxs_sample_y,
        shutter=shutter,
        stroke_height=stroke_height,
        stroke_spacing=stroke_spacing,
        n_strokes=n_strokes,
        both_directions=both_directions
    )))


