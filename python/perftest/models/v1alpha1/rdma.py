import itertools as it
import re
import typing as t

from pydantic import Field, constr

from kube_custom_resource import schema

from ...config import settings
from ...errors import PodLogFormatError, PodResultsIncompleteError

from . import base


RDMA_BANDWIDTH_REGEX = re.compile(
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

RDMA_LATENCY_REGEX = re.compile(
    r"(?P<bytes>\d+)"
    r"\s+"
    r"(?P<iterations>\d+)"
    r"\s+"
    r"(?P<minimum>\d+(\.\d+)?)"
    r"\s+"
    r"(?P<maximum>\d+(\.\d+)?)"
    r"\s+"
    r"(?P<typical>\d+(\.\d+)?)"
    r"\s+"
    r"(?P<average>\d+(\.\d+)?)"
    r"\s+"
    r"(?P<stdev>\d+(\.\d+)?)"
    r"\s+"
    r"(?P<percentile_99>\d+(\.\d+)?)"
    r"\s+"
    r"(?P<percentile_99_9>\d+(\.\d+)?)"
)


class RDMAMode(str, schema.Enum):
    """
    Enumeration of possible modes for the RDMA benchmarks.
    """
    READ = "read"
    WRITE = "write"


class RDMASpec(base.BenchmarkSpec):
    """
    Defines the common parameters for RDMA benchmarks.
    """
    image: constr(min_length = 1) = Field(
        f"{settings.default_image_prefix}perftest:{settings.default_image_tag}",
        description = "The image to use for the benchmark."
    )
    image_pull_policy: base.ImagePullPolicy = Field(
        base.ImagePullPolicy.IF_NOT_PRESENT,
        description = "The pull policy for the image."
    )
    mode: RDMAMode = Field(
        RDMAMode.READ,
        description = "The mode for the test."
    )
    iterations: schema.conint(ge = 5) = Field(
        1000,
        description = "The number of iterations for each message size."
    )
    extra_args: t.List[constr(min_length = 1)] = Field(
        default_factory = list,
        description = "Extra arguments for the command."
    )


class RDMAStatus(base.BenchmarkStatus):
    """
    Base class for the status of an RDMA benchmark.
    """
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


class RDMABenchmark(base.Benchmark, abstract = True):
    """
    Base class for RDMA benchmarks.
    """
    spec: RDMASpec = Field(
        ...,
        description = "The parameters for the benchmark."
    )
    status: RDMAStatus = Field(
        default_factory = RDMAStatus,
        description = "The status of the benchmark."
    )

    async def pod_modified(
        self,
        pod: t.Dict[str, t.Any],
        fetch_pod_log: t.Callable[[], t.Awaitable[str]]
    ):
        component = pod["metadata"]["labels"][settings.component_label]
        pod_phase = pod.get("status", {}).get("phase", "Unknown")
        # If the pod is in the running phase, record the info
        if pod_phase == "Running":
            setattr(self.status, f"{component}_pod", base.PodInfo.from_pod(pod))
        # When a client pod succeeds, record the pod log
        elif component == "client" and pod_phase == "Succeeded":
            self.status.client_log = await fetch_pod_log()

    def extract_result(self, pod_log_lines: t.Iterable[str]):
        """
        Extract a result from the client pod log.
        """
        raise NotImplementedError

    def summarise(self):
        # If the client log has not yet been recorded, bail
        if not self.status.client_log:
            raise PodResultsIncompleteError("client pod has not recorded logs yet")
        self.extract_result(self.status.client_log.splitlines())


class RDMABandwidthSpec(RDMASpec):
    """
    Defines the parameters for the RDMA bandwidth benchmark.
    """
    qps: schema.conint(gt = 0) = Field(
        1,
        description = "The number of Queue Pairs (QPs) to use."
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


class RDMABandwidthStatus(RDMAStatus):
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


class RDMABandwidth(
    RDMABenchmark,
    subresources = {"status": {}},
    printer_columns = [
        {
            "name": "Host Network",
            "type": "boolean",
            "jsonPath": ".spec.hostNetwork",
        },
        {
            "name": "Network Name",
            "type": "string",
            "jsonPath": ".spec.networkName",
        },
        {
            "name": "MTU",
            "type": "integer",
            "jsonPath": ".spec.mtu",
            "priority": 1,
        },
        {
            "name": "Mode",
            "type": "string",
            "jsonPath": ".spec.mode",
        },
        {
            "name": "QPs",
            "type": "integer",
            "jsonPath": ".spec.qps",
        },
        {
            "name": "Iterations",
            "type": "string",
            "jsonPath": ".spec.iterations",
        },
        {
            "name": "Status",
            "type": "string",
            "jsonPath": ".status.phase",
        },
        {
            "name": "Server IP",
            "type": "string",
            "jsonPath": ".status.serverPod.podIp",
            "priority": 1,
        },
        {
            "name": "Client IP",
            "type": "string",
            "jsonPath": ".status.clientPod.podIp",
            "priority": 1,
        },
        {
            "name": "Started",
            "type": "date",
            "jsonPath": ".status.startedAt",
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

    def extract_result(self, pod_log_lines: t.Iterable[str]):
        # Drop the lines from the log until we reach the start of the results
        lines = it.dropwhile(lambda l: not l.strip().startswith("#bytes"), pod_log_lines)
        # Skip the header
        _ = next(lines)
        # Collect the results for each message size along with the peak result
        results = []
        peak_result = None
        for line in lines:
            match = RDMA_BANDWIDTH_REGEX.search(line.strip())
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


class RDMALatencyResult(schema.BaseModel):
    """
    Represents an RDMA latency result.
    """
    bytes: schema.conint(gt = 0) = Field(
        ...,
        description = "The number of bytes."
    )
    iterations: schema.conint(gt = 0) = Field(
        ...,
        description = "The number of iterations."
    )
    minimum: schema.confloat(ge = 0) = Field(
        ...,
        description = "The minimum latency in usecs."
    )
    maximum: schema.confloat(ge = 0) = Field(
        ...,
        description = "The maximum latency in usecs."
    )
    typical: schema.confloat(ge = 0) = Field(
        ...,
        description = "The typical latency in usecs."
    )
    average: schema.confloat(ge = 0) = Field(
        ...,
        description = "The average latency in usecs."
    )
    stdev: schema.confloat(ge = 0) = Field(
        ...,
        description = "The standard deviation of the latency in usecs."
    )
    percentile_99: schema.confloat(ge = 0) = Field(
        ...,
        description = "The 99% percentile of the latency in usecs."
    )
    percentile_99_9: schema.confloat(ge = 0) = Field(
        ...,
        description = "The 99.9% percentile of the latency in usecs."
    )


class RDMALatencyStatus(RDMAStatus):
    """
    Represents the status of the RDMA latency benchmark.
    """
    results: t.List[RDMALatencyResult] = Field(
        default_factory = list,
        description = "List of results for each message length."
    )
    minimum_average_latency: t.Optional[constr(min_length = 1)] = Field(
        None,
        description = (
            "The minimum average latency for any message length. "
            "Used as a headline result."
        )
    )


class RDMALatency(
    RDMABenchmark,
    plural_name = "rdmalatencies",
    subresources = {"status": {}},
    printer_columns = [
        {
            "name": "Host Network",
            "type": "boolean",
            "jsonPath": ".spec.hostNetwork",
        },
        {
            "name": "Network Name",
            "type": "string",
            "jsonPath": ".spec.networkName",
        },
        {
            "name": "MTU",
            "type": "integer",
            "jsonPath": ".spec.mtu",
            "priority": 1,
        },
        {
            "name": "Mode",
            "type": "string",
            "jsonPath": ".spec.mode",
        },
        {
            "name": "Iterations",
            "type": "string",
            "jsonPath": ".spec.iterations",
        },
        {
            "name": "Status",
            "type": "string",
            "jsonPath": ".status.phase",
        },
        {
            "name": "Server IP",
            "type": "string",
            "jsonPath": ".status.serverPod.podIp",
            "priority": 1,
        },
        {
            "name": "Client IP",
            "type": "string",
            "jsonPath": ".status.clientPod.podIp",
            "priority": 1,
        },
        {
            "name": "Started",
            "type": "date",
            "jsonPath": ".status.startedAt",
        },
        {
            "name": "Finished",
            "type": "date",
            "jsonPath": ".status.finishedAt",
        },
        {
            "name": "Min Avg Latency",
            "type": "string",
            "jsonPath": ".status.minimumAverageLatency",
        },
    ]
):
    """
    Custom resource for running an RDMA latency benchmark.
    """
    status: RDMALatencyStatus = Field(
        default_factory = RDMALatencyStatus,
        description = "The status of the benchmark."
    )

    def extract_result(self, pod_log_lines: t.Iterable[str]):
        # Drop the lines from the log until we reach the start of the results
        lines = it.dropwhile(lambda l: not l.strip().startswith("#bytes"), pod_log_lines)
        # Skip the header
        _ = next(lines)
        # Collect the results for each message size along with the peak result
        results = []
        min_result = None
        for line in lines:
            match = RDMA_LATENCY_REGEX.search(line.strip())
            if match is not None:
                result = RDMALatencyResult(
                    bytes = match.group("bytes"),
                    iterations = match.group("iterations"),
                    minimum = match.group("minimum"),
                    maximum = match.group("maximum"),
                    typical = match.group("typical"),
                    average = match.group("average"),
                    stdev = match.group("stdev"),
                    percentile_99 = match.group("percentile_99"),
                    percentile_99_9 = match.group("percentile_99_9")
                )
                results.append(result)
                if not min_result or result.average < min_result.average:
                    min_result = result
            else:
                continue
        if results:
            self.status.results = results
        else:
            raise PodLogFormatError("unable to locate results in pod log")
        # Format the peak result for display
        self.status.minimum_average_latency = f"{min_result.average} usec"
