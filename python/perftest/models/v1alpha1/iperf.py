import itertools as it
import re
import typing as t

from pydantic import Field, validator, constr

from kube_custom_resource import schema

from ...config import settings
from ...errors import PodLogFormatError, PodResultsIncompleteError
from ...utils import format_amount

from . import base


class IPerfSpec(schema.BaseModel):
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
    host_network: bool = Field(
        False,
        description = "Indicates whether to use host networking or not."
    )
    server_service: bool = Field(
        False,
        description = "Indicates whether to access the server via a service or not."
    )
    duration: schema.conint(gt = 0) = Field(
        ...,
        description = "The duration of the benchmark."
    )
    streams: schema.conint(gt = 0) = Field(
        ...,
        description = "The number of streams to use."
    )
    buffer_size: schema.conint(gt = 0) = Field(
        128 * 1024,  # 128K
        description = "The length of the read/write buffer in bytes."
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
        description = "The average bandwidth for the transfer."
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
            "name": "Server Service",
            "type": "string",
            "jsonPath": ".spec.serverService",
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
            "name": "Buffer Size",
            "type": "integer",
            "jsonPath": ".spec.bufferSize",
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
        """
        Update the status of this benchmark to reflect a modification to one of its pods.

        Receives the pod instance and an async function that can be called to get the pod log.
        """
        # When a pod succeeds, derive a result from the pod log and save it
        pod_phase = pod.get("status", {}).get("phase", "Unknown")
        if pod_phase == "Succeeded":
            pod_log = await fetch_pod_log()
            # Drop the lines from the log until we reach the start of the results
            lines = it.dropwhile(lambda l: re.match(r"^\[ *ID\]", l) is None, pod_log.splitlines())
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
                raise PodLogFormatError("pod log is not of the expected format", pod_log)
            # There should only ever be one completed pod for iperf, so we just override the result
            self.status.result = IPerfResult(
                streams = stream_results,
                # If there is no explicit sum result, use the result from the single stream
                sum = sum_result or next(iter(stream_results.values()))
            )

    def summarise(self):
        """
        Update the status of this benchmark with overall results.
        """
        # If the result is not set yet, bail
        if not self.status.result:
            raise PodResultsIncompleteError("client pod has not recorded a result yet")
        # For the summary result, we use the combined bandwidth
        # However we want to convert it from Kbits/sec to something friendlier
        amount, prefix = format_amount(self.status.result.sum.bandwidth, "K")
        self.status.summary_result = f"{amount} {prefix}bits/sec"
