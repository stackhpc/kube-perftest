import itertools as it
import re
import typing as t

from pydantic import Field, constr

from kube_custom_resource import schema

from ...config import settings
from ...errors import PodLogFormatError, PodResultsIncompleteError
from ...template import Loader
from ...utils import format_amount

from . import base


class MPIPingPongSpec(schema.BaseModel):
    """
    Defines the parameters for the iperf benchmark.
    """
    image: constr(min_length = 1) = Field(
        f"{settings.default_image_prefix}mpi-benchmarks:{settings.default_image_tag}",
        description = "The image to use for the benchmark."
    )
    image_pull_policy: base.ImagePullPolicy = Field(
        base.ImagePullPolicy.IF_NOT_PRESENT,
        description = "The pull policy for the image."
    )


class MPIPingPongStatus(base.BenchmarkStatus):
    """
    Represents the status of the iperf benchmark.
    """


class MPIPingPong(
    base.Benchmark,
    subresources = {"status": {}},
    printer_columns = [
        {
            "name": "Status",
            "type": "string",
            "jsonPath": ".status.phase",
        },
        {
            "name": "Finished",
            "type": "date",
            "jsonPath": ".status.finishedAt",
        },
    ]
):
    """
    Custom resource for running an iperf benchmark.
    """
    spec: MPIPingPongSpec = Field(
        ...,
        description = "The parameters for the benchmark."
    )
    status: MPIPingPongStatus = Field(
        default_factory = MPIPingPongStatus,
        description = "The status of the benchmark."
    )

    async def pod_modified(
        self,
        pod: t.Dict[str, t.Any],
        fetch_pod_log: t.Callable[[], t.Awaitable[str]]
    ):
        pass

    def summarise(self):
        """
        Update the status of this benchmark with overall results.
        """
        pass
