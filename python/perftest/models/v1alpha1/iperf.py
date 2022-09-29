import itertools as it
import re
import typing as t

from pydantic import Field, constr

from kube_custom_resource import schema

from ...config import settings
from ...errors import PodLogFormatError, PodResultsIncompleteError
from ...utils import format_amount

from . import base


class IPerfSpec(base.BenchmarkSpec):
    """
    Defines the parameters for the iperf benchmark.
    """
    image: constr(min_length = 1) = Field(
        f"{settings.default_image_prefix}iperf:{settings.default_image_tag}",
        description = "The image to use for the benchmark."
    )
    image_pull_policy: base.ImagePullPolicy = Field(
        base.ImagePullPolicy.IF_NOT_PRESENT,
        description = "The pull policy for the image."
    )
    duration: schema.conint(gt = 0) = Field(
        ...,
        description = "The duration of the benchmark."
    )
    streams: schema.conint(gt = 0) = Field(
        ...,
        description = "The number of streams to use."
    )


class IPerfSingleResult(schema.BaseModel):
    """
    Represents the result of an individual iperf stream or summary.
    """
    transfer: schema.conint(ge = 0) = Field(
        ...,
        description = "The amount of data transferred in KBytes."
    )
    bandwidth: schema.conint(ge = 0) = Field(
        ...,
        description = "The average bandwidth for the transfer in Kbits/sec."
    )


class IPerfResult(schema.BaseModel):
    """
    Represents the result of an iperf benchmark.
    """
    streams: schema.Dict[str, IPerfSingleResult] = Field(
        ...,
        description = "Results from the individual streams, indexed by stream ID."
    )
    sum: IPerfSingleResult = Field(
        ...,
        description = "Combined result from all the streams."
    )


class IPerfStatus(base.BenchmarkStatus):
    """
    Represents the status of the iperf benchmark.
    """
    summary_result: t.Optional[schema.IntOrString] = Field(
        None,
        description = "The summary result for the benchmark, used for display."
    )
    result: t.Optional[IPerfResult] = Field(
        None,
        description = "The complete result for the benchmark."
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


class IPerf(
    base.Benchmark,
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
            "name": "Duration",
            "type": "integer",
            "jsonPath": ".spec.duration",
        },
        {
            "name": "Streams",
            "type": "integer",
            "jsonPath": ".spec.streams",
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
            "name": "Result",
            "type": "string",
            "jsonPath": ".status.summaryResult",
        },
    ]
):
    """
    Custom resource for running an iperf benchmark.
    """
    spec: IPerfSpec = Field(
        ...,
        description = "The parameters for the benchmark."
    )
    status: IPerfStatus = Field(
        default_factory = IPerfStatus,
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
        # Compute the result from the client log
        # Drop the lines from the log until we reach the start of the results
        lines = it.dropwhile(lambda l: re.match(r"^\[ *ID\]", l) is None, self.status.client_log.splitlines())
        # Drop the header line
        _ = next(lines)
        # Collect stream results until the end of the log
        stream_results = {}
        for line in lines:
            match = re.search(r"^\[ *([a-zA-Z0-9]+)\].*?(\d+) KBytes +(\d+) Kbits/sec", line)
            if match is not None:
                stream_results[match.group(1)] = IPerfSingleResult(
                    transfer = match.group(2),
                    bandwidth = match.group(3)
                )
            else:
                continue
        # Extract the sum result if it is present (single stream runs don't have one)
        sum_result = stream_results.pop("SUM", None)
        # Ensure that the result has the correct number of streams
        if (
            len(stream_results) != self.spec.streams or
            (self.spec.streams > 1 and not sum_result)
        ):
            raise PodLogFormatError("pod log is not of the expected format")
        # Store the detailed result
        self.status.result = IPerfResult(
            streams = stream_results,
            # If there is no explicit sum result, use the result from the single stream
            sum = sum_result or next(iter(stream_results.values()))
        )
        # For the summary result, we use the combined bandwidth
        # However we want to convert it from Kbits/sec to something friendlier
        amount, prefix = format_amount(self.status.result.sum.bandwidth, "K", quotient = 1000)
        self.status.summary_result = f"{amount} {prefix}bits/sec"
