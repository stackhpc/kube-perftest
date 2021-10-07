from importlib.metadata import entry_points

import kopf


#: The name of the entry point to use for loading benchmarks
BENCHMARKS_ENTRY_POINT = 'perftest.benchmarks'


@kopf.on.startup()
def init_benchmarks(**kwargs):
    """
    Initialises the benchmarks specified in the entry point.
    """
    logger = kwargs['logger']
    # Load each of the benchmarks specified in the entrypoints
    # This should have the side effect of registering the required kopf handlers
    benchmarks = [ep.load() for ep in entry_points()[BENCHMARKS_ENTRY_POINT]]
    # kopf startup handlers are called before the login handler, so we need to authenticate
    kopf.login_via_client(**kwargs)
    # Register the CRD for each benchmark
    for benchmark in benchmarks:
        benchmark.register_crd()
        logger.info(f"Registered benchmark {benchmark.full_name}.")
