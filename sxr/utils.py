import time
from functools import wraps

def retry(tries=5, logger=None):
    """
    Retry calling the decorated function using an exponential backoff.

    Parameters
    ----------
        exceptions: The exception to check. may be a tuple of
            exceptions to check.
        tries: Number of times to try (not retry) before giving up.
        delay: Initial delay between retries in seconds.
        backoff: Backoff multiplier (e.g. value of 2 will double the delay
            each retry).
        logger: Logger to use. If None, print.
    """
    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries = tries
            while mtries >= 1:
                status = f(*args, **kwargs)
                if status.success:
                    break
                else:
                    mtries -= 1
            return status
        return f_retry  # true decorator
    return deco_retry
