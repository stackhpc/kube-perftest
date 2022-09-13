import itertools as it
import re
import typing as t

from pydantic import Field, constr

from kube_custom_resource import schema

from ...config import settings
from ...errors import PodLogFormatError, PodResultsIncompleteError

from . import base


RDMA_RESULT_REGEX = re.compile(
    r"(?P<bytes>\d+)"
    r"\s+"
    r"(?P<iterations>\d+)"
    r"\s+"
    r"(?P<bw_peak>\d+(\.\d+)?)"
    r"\s+"
    r"(?P<bw_avg>\d+(\.\d+)?)"
    r"\s+"
    r"(?P<msg_rate>\d+(\.\d+)?)"
)


class RDMABandwidthMode(str, schema.Enum):
    """
    Enumeration of possible modes for the RDMA bandwidth benchmark.
    """
    READ = "read"
    WRITE = "write"


class RDMABandwidthSpec(schema.BaseModel):
    """
    Defines the parameters for the RDMA bandwidth benchmark.
    """
    image: constr(min_length = 1) = Field(
        f"{settings.default_image_prefix}perftest:{settings.default_image_tag}",
        description = "The image to use for the benchmark."
    )
    image_pull_policy: base.ImagePullPolicy = Field(
        base.ImagePullPolicy.IF_NOT_PRESENT,
        description = "The pull policy for the image."
    )
    mode: RDMABandwidthMode = Field(
        RDMABandwidthMode.READ,
        description = "The mode for the test."
    )
    rdma_shared_device_name: constr(min_length = 1) = Field(
        ...,
        description = "The name of the RDMA shared device to use."
    )


class RDMABandwidthResult(schema.BaseModel):
    """
    Represents an RDMA bandwidth result.
    """
    bytes: schema.conint(gt = 0) = Field(
        ...,
        description = "The number of bytes."
    )
    iterations: schema.conint(gt = 0) = Field(
        ...,
        description = "The number of iterations."
    )
    peak_bandwidth: schema.confloat(ge = 0) = Field(
        ...,
        description = "The peak bandwidth in Gbit/sec."
    )
    average_bandwidth: schema.confloat(ge = 0) = Field(
        ...,
        description = "The average bandwidth in Gbit/sec."
    )
    message_rate: schema.confloat(ge = 0) = Field(
        ...,
        description = "The message rate in Mpps."
    )


class RDMABandwidthStatus(base.BenchmarkStatus):
    """
    Represents the status of the RDMA bandwidth benchmark.
    """
    results: t.List[RDMABandwidthResult] = Field(
        default_factory = list,
        description = "List of results for each message length."
    )
    peak_bandwidth: t.Optional[constr(min_length = 1)] = Field(
        None,
        description = (
            "The peak bandwidth achieved during the benchmark. "
            "Used as a headline result."
        )
    )
    client_log: t.Optional[constr(min_length = 1)] = Field(
        None,
        description = "The raw pod log of the client pod."
    )
    server_pod: t.Optional[base.PodInfo] = Field(
        None,
        description = "Pod information for the server pod."
    )
    client_pod: t.Optional[base.PodInfo] = Field(
        None,
        description = "Pod information for the client pod."
    )


class RDMABandwidth(
    base.Benchmark,
    subresources = {"status": {}},
    printer_columns = [
        {
            "name": "Mode",
            "type": "string",
            "jsonPath": ".spec.mode",
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
    Custom resource for running an RDMA bandwidth benchmark.
    """
    spec: RDMABandwidthSpec = Field(
        ...,
        description = "The parameters for the benchmark."
    )
    status: RDMABandwidthStatus = Field(
        default_factory = RDMABandwidthStatus,
        description = "The status of the benchmark."
    )

    async def pod_modified(
        self,
        pod: t.Dict[str, t.Any],
        fetch_pod_log: t.Callable[[], t.Awaitable[str]]
    ):
        pod_phase = pod.get("status", {}).get("phase", "Unknown")
        # If the pod is in the running phase, record the info
        if pod_phase == "Running":
            component = pod["metadata"]["labels"][settings.component_label]
            setattr(self.status, f"{component}_pod", base.PodInfo.from_pod(pod))
        # When a pod succeeds, record the pod log
        # Note that only the client pod ever succeeds as the server is forcibly terminated
        elif pod_phase == "Succeeded":
            self.status.client_log = await fetch_pod_log()

    def summarise(self):
        # If the client log has not yet been recorded, bail
        if not self.status.client_log:
            raise PodResultsIncompleteError("client pod has not recorded logs yet")
        # Drop the lines from the log until we reach the start of the results
        lines = it.dropwhile(
            lambda l: not l.strip().startswith("#bytes"),
            self.status.client_log.splitlines()
        )
        # Skip the header
        _ = next(lines)
        # Collect the results for each message size along with the peak result
        results = []
        peak_result = None
        for line in lines:
            match = RDMA_RESULT_REGEX.search(line.strip())
            if match is not None:
                result = RDMABandwidthResult(
                    bytes = match.group("bytes"),
                    iterations = match.group("iterations"),
                    peak_bandwidth = match.group("bw_peak"),
                    average_bandwidth = match.group("bw_avg"),
                    message_rate = match.group("msg_rate")
                )
                results.append(result)
                if not peak_result or result.peak_bandwidth > peak_result.peak_bandwidth:
                    peak_result = result
            else:
                continue
        if results:
            self.status.results = results
        else:
            raise PodLogFormatError("unable to locate results in pod log")
        # Format the peak result for display
        self.status.peak_bandwidth = f"{peak_result.peak_bandwidth} Gbit/sec"
