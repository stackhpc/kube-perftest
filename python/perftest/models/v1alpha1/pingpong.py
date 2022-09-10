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

MPI_PINGPONG_UNITS = re.compile(
    r"t\[(?P<time>[^\]]+)\]"
    r"\s+"
    r"(?P<bandwidth>\w?bytes/sec)"
)
MPI_PINGPONG_RESULT = re.compile(
    r"^"
    r"(?P<bytes>\d+)"
    r"\s+"
    r"(?P<repetitions>\d+)"
    r"\s+"
    r"(?P<time>\d+\.\d+)"
    r"\s+"
    r"(?P<bandwidth>\d+\.\d+)"
)


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
    ssh_port: schema.conint(gt = 0) = Field(
        2222,
        description = "The port to use for SSH."
    )
    host_network: bool = Field(
        False,
        description = "Indicates whether to use host networking or not."
    )


class MPIPingPongResult(schema.BaseModel):
    """
    Represents an individual MPI pingpong result.
    """
    bytes: schema.conint(ge = 0) = Field(
        ...,
        description = "The message length in bytes."
    )
    repetitions: schema.conint(ge = 0) = Field(
        ...,
        description = "The number of repetitions that were performed."
    )
    time: schema.confloat(ge = 0) = Field(
        ...,
        description = "The average time until a reply is received."
    )
    bandwidth: schema.confloat(ge = 0) = Field(
        ...,
        description = "The average bandwidth that was achieved."
    )


class MPIPingPongStatus(base.BenchmarkStatus):
    """
    Represents the status of the iperf benchmark.
    """
    bandwidth_units: t.Optional[constr(min_length = 1)] = Field(
        None,
        description = "The units that the bandwidth is reported in."
    )
    time_units: t.Optional[constr(min_length = 1)] = Field(
        None,
        description = "The units that the time is reported in."
    )
    results: t.List[MPIPingPongResult] = Field(
        default_factory = list,
        description = "List of results for each message length."
    )
    peak_bandwidth: t.Optional[constr(min_length = 1)] = Field(
        None,
        description = (
            "The peak bandwidth achieved during the benchmark for any given message length. "
            "Used as a headline result."
        )
    )
    master_log: t.Optional[constr(min_length = 1)] = Field(
        None,
        description = "The raw pod log of the MPI master pod."
    )
    master_pod: t.Optional[base.PodInfo] = Field(
        None,
        description = "Pod information for the MPI master pod."
    )
    worker_pods: schema.Dict[str, base.PodInfo] = Field(
        default_factory = dict,
        description = "Pod information for the worker pods, indexed by pod name."
    )


class MPIPingPong(
    base.Benchmark,
    subresources = {"status": {}},
    printer_columns = [
        {
            "name": "Host Network",
            "type": "boolean",
            "jsonPath": ".spec.hostNetwork",
        },
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
        {
            "name": "Peak Bandwidth",
            "type": "string",
            "jsonPath": ".status.peakBandwidth",
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
        pod_phase = pod.get("status", {}).get("phase", "Unknown")
        pod_component = pod["metadata"]["labels"][settings.component_label]
        if pod_component == "master":
            if pod_phase == "Running":
                self.status.master_pod = base.PodInfo.from_pod(pod)
            elif pod_phase == "Succeeded":
                self.status.master_log = await fetch_pod_log()
        elif pod_phase == "Running":
            self.status.worker_pods[pod["metadata"]["name"]] = base.PodInfo.from_pod(pod)

    def summarise(self):
        """
        Update the status of this benchmark with overall results.
        """
        if not self.status.master_log:
            raise PodResultsIncompleteError("master pod has not recorded a log yet")
        # Drop the lines from the log until we reach the start of the results
        lines = it.dropwhile(
            lambda l: not l.strip().startswith("#bytes"),
            self.status.master_log.splitlines()
        )
        # Extract the bandwidth units from the header
        match = MPI_PINGPONG_UNITS.search(next(lines))
        if match is not None:
            self.status.bandwidth_units = match.group("bandwidth")
            self.status.time_units = match.group("time")
        else:
            raise PodLogFormatError("unable to get bandwidth units from pod log")
        # Collect the results for each message size along with the peak result
        results = []
        peak_result = None
        for line in lines:
            match = MPI_PINGPONG_RESULT.search(line.strip())
            if match is not None:
                result = MPIPingPongResult(
                    bytes = match.group("bytes"),
                    repetitions = match.group("repetitions"),
                    time = match.group("time"),
                    bandwidth = match.group("bandwidth")
                )
                results.append(result)
                if not peak_result or result.bandwidth > peak_result.bandwidth:
                    peak_result = result
            else:
                break
        if results:
            self.status.results = results
        else:
            raise PodLogFormatError("unable to locate results in pod log")
        # Format the peak result for display
        self.status.peak_bandwidth = f"{peak_result.bandwidth} {self.status.bandwidth_units}"
