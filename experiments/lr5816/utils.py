import logging
from functools import wraps

from .exceptions import NotCalibratedError
# Decorators

logger = logging.getLogger(__name__)

def calibrated(method):
    """Checks to make sure the wrapped method is run when the object is
    calibrated.
    """
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        if not self.calibrated:
            raise NotCalibratedError('"{0}" is not calibrated!'.format(
                self.name))
        return method(self, *args, **kwargs)
    return wrapped
