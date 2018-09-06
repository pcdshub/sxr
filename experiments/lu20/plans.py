import uuid
import logging
import time

import pandas as pd
from bluesky.plan_stubs import one_nd_step, abs_set, wait as plan_wait
from bluesky.plans import scan, inner_product_scan, rel_scan
from bluesky.preprocessors import stub_wrapper

logger = logging.getLogger(__name__)

def rel_smooth_sweep_test(mot_x, origin, end):
    yield from rel_scan([], mot_x, origin, end)
