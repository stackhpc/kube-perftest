class Error(Exception):
    """
    Base class for benchmark errors.
    """


class PodLogFormatError(Error):
    """
    Raised when the pod log is not of the expected format to extract a result.
    """


class PodResultsIncompleteError(Error):
    """
    Raised when the overall result cannot be calculated because the individual pod
    results are incomplete.
    """
