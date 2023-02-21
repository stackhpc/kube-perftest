import itertools as it
import json
import re
import typing as t

from pydantic import Field, constr

from kube_custom_resource import schema

from ...config import settings
from ...errors import PodLogFormatError, PodResultsIncompleteError

from . import base

class FioRW(str, schema.Enum):
    """
    Enumeration of supported Fio rw modes.
    """
    READ = "read"
    WRITE = "write"
    RANDREAD = "randread"
    RANDWRITE = "randwrite"
    RW_READWRITE = "rw,readwrite"
    RANDRW = "randrw"

class FioDirect(int, schema.Enum):
    """
    Enumeration of supported Fio direct Bools.
    """
    TRUE = 1
    FALSE = 0

class FioIOEngine(str, schema.Enum):
    """
    Enumeration of supported Fio ioengines.
    """
    LIBAIO = "libaio"

class FioSpec(base.BenchmarkSpec):
    """
    Defines the parameters for the Fio benchmark.
    """
    image: constr(min_length = 1) = Field(
        f"{settings.default_image_prefix}fio:{settings.default_image_tag}",
        description = "The image to use for the benchmark."
    )
    image_pull_policy: base.ImagePullPolicy = Field(
        base.ImagePullPolicy.IF_NOT_PRESENT,
        description = "The pull policy for the image."
    )
    fio_port: schema.conint(ge = 1024) = Field(
        8765,
        description = "The port that the Fio sever listens on."
    )
    volume_claim_template: schema.Dict[str, t.Any] = Field(
        default_factory = dict,
        description = "The template that describes the PVC to mount on workers."
    )
    num_workers: schema.conint(gt = 0) = Field(
        1,
        description = "The number of Fio workers."
    )
    # Fio config options
    rw: FioRW = Field(
        FioRW.READ,
        description = "The value of the Fio rw config option."
    )
    bs: constr(regex = "\\d+(K|M|G|T|P)?") = Field(
        "4M",
        description = "The value of the Fio bs config option."
    )
    iodepth: schema.conint(gt = 0) = Field(
        1,
        description = "The value of the Fio iodepth config option."
    )
    ioengine: schema.conint(gt = 0) = Field(
        1,
        description = "The value of the Fio iodepth config option."
    )
    nrfiles: schema.conint(gt = 0) = Field(
        1,
        description = "The value of the Fio nrfiles config option."
    )
    rwmixread: schema.conint(ge = 0, le = 100) = Field(
        50,
        description = "The value of the Fio rwmixread config option."
    )
    percentage_random: schema.conint(ge = 0, le = 100) = Field(
        100,
        description = "The value of the Fio percentage_random config option."
    )
    direct: FioDirect = Field(
        FioDirect.TRUE,
        description = "The value of the Fio direct config option."
    )
    ioengine: FioIOEngine = Field(
        FioIOEngine.LIBAIO,
        description = "The value of the Fio ioengine config option."
    )
    runtime: constr(regex = "\\d+(D|H|M|s|ms|us)?") = Field(
        "30s",
        description = "The value of the Fio runtime config option."
    )
    num_jobs: schema.conint(gt = 0) = Field(
        1,
        description = "The value of the Fio numjobs config option."
    )
    size: constr(regex = "\\d+(K|M|G|T|P)?") = Field(
        "10G",
        description = "The value of the Fio size config option."
    )
    thread: bool = Field(
        False,
        description = "Fio use threads config option."
    )


class FioResult(schema.BaseModel):
    """
    Represents an individual Fio result.
    """
    read_bw: schema.confloat(ge = 0) = Field(
        ...,
        description = "The aggregate read bandwidth."
    )
    read_iops: schema.confloat(ge = 0) = Field(
        ...,
        description = "The aggregate read IOPS."
    )
    read_lat_ns_mean: schema.confloat(ge = 0) = Field(
        ...,
        description = "The aggregate mean read latency."
    )
    read_lat_ns_stddev: schema.confloat(ge = 0) = Field(
        ...,
        description = "The aggregate read latency standard deviation."
    )
    write_bw: schema.confloat(ge = 0) = Field(
        ...,
        description = "The aggregate write bandwidth."
    )
    write_iops: schema.confloat(ge = 0) = Field(
        ...,
        description = "The aggregate write IOPS."
    )
    write_lat_ns_mean: schema.confloat(ge = 0) = Field(
        ...,
        description = "The aggregate mean read latency."
    )
    write_lat_ns_stddev: schema.confloat(ge = 0) = Field(
        ...,
        description = "The aggregate read latency standard deviation."
    )
    
class FioStatus(base.BenchmarkStatus):
    """
    Represents the status of the Fio benchmark.
    """
    result: t.Optional[FioResult] = Field(
        None,
        description = "The result of the benchmark."
    )
    master_pod: t.Optional[base.PodInfo] = Field(
        None,
        description = "Pod information for the Fio master pod."
    )
    worker_pods: schema.Dict[str, base.PodInfo] = Field(
        default_factory = dict,
        description = "Pod information for the worker pods, indexed by pod name."
    )
    client_log: t.Optional[constr(min_length = 1)] = Field(
        None,
        description = "The raw pod log of the client pod."
    )

class Fio(
    base.Benchmark,
    subresources = {"status": {}},
    printer_columns = [
        {
            "name": "Num Jobs",
            "type": "integer",
            "jsonPath": ".spec.numJobs",
        },
        {
            "name": "Num Workers",
            "type": "integer",
            "jsonPath": ".spec.numWorkers",
        },
        {
            "name": "RW",
            "type": "string",
            "jsonPath": ".spec.rw",
        },
        {
            "name": "BS",
            "type": "string",
            "jsonPath": ".spec.bs",
        },
        {
            "name": "Pct Read",
            "type": "string",
            "jsonPath": ".spec.rwmixread",
        },
        {
            "name": "Pct Random",
            "type": "string",
            "jsonPath": ".spec.percentageRandom",
        },
        {
            "name": "Status",
            "type": "string",
            "jsonPath": ".status.phase",
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
            "name": "Read Bandwidth",
            "type": "number",
            "jsonPath": ".status.result.readBw",
        },
        {
            "name": "Read IOPS",
            "type": "number",
            "jsonPath": ".status.result.readIops",
        },
        {
            "name": "Write Bandwidth",
            "type": "number",
            "jsonPath": ".status.result.writeBw",
        },
        {
            "name": "Write IOPS",
            "type": "number",
            "jsonPath": ".status.result.writeIops",
        }
    ]
):
    """
    Custom resource for running an iperf benchmark.
    """
    spec: FioSpec = Field(
        ...,
        description = "The parameters for the benchmark."
    )
    status: FioStatus = Field(
        default_factory = FioStatus,
        description = "The status of the benchmark."
    )

    async def pod_modified(
        self,
        pod: t.Dict[str, t.Any],
        fetch_pod_log: t.Callable[[], t.Awaitable[str]]
    ):
        pod_phase = pod.get("status", {}).get("phase", "Unknown")
        pod_component = pod["metadata"]["labels"][settings.component_label]
        if pod_phase == "Running":
            if pod_component == "master":
                self.status.master_pod = base.PodInfo.from_pod(pod)
            else:
                self.status.worker_pods[pod["metadata"]["name"]] = base.PodInfo.from_pod(pod)
        elif pod_phase == "Succeeded":
            self.status.client_log = await fetch_pod_log()

    def summarise(self):
        # If the client log has not yet been recorded, bail
        if not self.status.client_log:
            raise PodResultsIncompleteError("master pod has not recorded a result yet")
        # Compute the result from the client log
        try:
            fio_json = json.loads(self.status.client_log)
        except:
            raise PodLogFormatError("pod log is not of the expected format")

        if len(fio_json['client_stats']) == 1:
            # Single worker, single process doesn't have an
            # 'All clients' log section
            aggregate_data = fio_json['client_stats'][0]
        else:
            aggregate_data = [i for i in fio_json['client_stats'] if i['jobname'] == 'All clients'][0]

        self.status.result = FioResult(
            read_bw = aggregate_data['read']['bw'],
            read_iops = aggregate_data['read']['iops'],
            read_lat_ns_mean = aggregate_data['read']['lat_ns']['mean'],
            read_lat_ns_stddev = aggregate_data['read']['lat_ns']['stddev'],
            write_bw = aggregate_data['write']['bw'],
            write_iops = aggregate_data['write']['iops'],
            write_lat_ns_mean = aggregate_data['write']['lat_ns']['mean'],
            write_lat_ns_stddev = aggregate_data['write']['lat_ns']['stddev']
        )
