import logging

logger = logging.getLogger(__name__)


class SxrPythonException(Exception):
    """Base exception class for the SXR-python environment."""
    pass


class InputError(SxrPythonException):
    """Exception raised when invalid inputs are provided."""
    pass
