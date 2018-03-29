import logging

logger = logging.getLogger(__name__)


class SxrPythonException(Exception):
    """Base exception class for the SXR-python environment."""
    pass


class InputError(SxrPythonException):
    """Exception raised when invalid inputs are provided."""
    pass


class Lr5816Error(SxrPythonException):
    """Base exception class for the run 16 LR58 mcgrain experiment."""
    pass


class NotCalibratedError(Lr5816Error):
    """Exception raised when there is no current calibration."""
    pass
