import logging

logger = logging.getLogger(__name__)

class SxrpyException(Exception):
    """
    Base exception class for the SXR-python environment.
    """
    pass

class InputError(Exception):
    """
    Exception raised when invalid inputs are provided.
    """
    pass
