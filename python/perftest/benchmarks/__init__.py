BENCHMARKS_API_GROUP = "perftest.stackhpc.com"


def ALL():
    """
    Returns a list of the available benchmarks.
    """
    from .fio import fio
    from .iperf import iperf
    from .suite import suite
    return [fio, iperf, suite]
