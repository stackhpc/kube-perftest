import kopf

from . import benchmarks


@kopf.on.startup()
def init_benchmarks(**kwargs):
    """
    Initialises the benchmarks specified in the entry point.
    """
    logger = kwargs['logger']
    # kopf startup handlers are called before the login handler, so we need to authenticate
    kopf.login_via_client(**kwargs)
    # Register the CRD for each benchmark
    for benchmark in benchmarks.ALL():
        benchmark.register_crd()
        logger.info(f"Registered benchmark {benchmark.full_name}.")
