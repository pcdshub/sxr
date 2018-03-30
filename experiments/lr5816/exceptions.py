import logging

from sxr.exceptions import SxrPythonException

logger = logging.getLogger(__name__)


class Lr5816Error(SxrPythonException):
    """Base exception class for the run 16 LR58 mcgrain experiment."""
    pass


class NotCalibratedError(Lr5816Error):
    """Exception raised when there is no current calibration."""
    pass


class InvalidSampleError(Lr5816Error):
    """Exception raised when an invalid sample number or index is inputted."""
    pass
