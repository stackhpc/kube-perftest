import re
import typing as t

from pydantic import Field, constr

from kube_custom_resource import schema

from ...config import settings
from ...errors import PodLogFormatError, PodResultsIncompleteError

from . import base


TIME_REGEX = re.compile(r"^(?P<type>real|user|sys)\s+(?P<time>\d+\.\d+)")


class MPITransport(str, schema.Enum):
    """
    Enumeration of supported MPI transports.
    """
    TCP = "TCP"
    RDMA = "RDMA"


class OpenFOAMProblemSize(str, schema.Enum):
    """
    Enumeration of possible OpenFOAM problem sizes.
    """
    SMALL = "S"
    MEDIUM = "M"
    EXTRA_LARGE = "XL"
    EXTRA_EXTRA_LARGE = "XXL"


class OpenFOAMIterativeMethod(str, schema.Enum):
    """
    Enumeration of possible OpenFOAM iterative methods.
    """
    FIXED_ITER = "fixedITER"
    FIXED_NORM = "fixedNORM"
    FOAM_DIC_PCG_FIXED_NORM = "FOAM-DIC-PCG.fixedNORM"
    FOAM_GAMG_PCG_FIXED_NORM = "FOAM-GAMG-PCG.fixedNORM"
    PETSC_AMG_CG_FIXED_NORM = "PETSc-AMG-CG.fixedNORM"
    PETSC_AMG_CG_FIXED_NORM_CACHING = "PETSc-AMG-CG.fixedNORM.caching"
    PETSC_ICC_CG_FIXED_NAME = "PETSc-ICC-CG.fixedNORM"


class OpenFOAMSpec(base.BenchmarkSpec):
    """
    Defines the parameters for the openFOAM benchmark.
    """
    image: constr(min_length = 1) = Field(
        f"{settings.default_image_prefix}openfoam:{settings.default_image_tag}",
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
    transport: MPITransport = Field(
        MPITransport.TCP,
        description = "The transport to use for the benchmark."
    )
    problem_size: OpenFOAMProblemSize = Field(
        OpenFOAMProblemSize.SMALL,
        description = "The problem size for the 3-D Lid Driven cavity flow benchmark."
    )
    iterative_method: OpenFOAMIterativeMethod = Field(
        OpenFOAMIterativeMethod.FIXED_NORM,
        description = "The iterative method for the 3-D Lid Driven cavity flow benchmark."
    )
    num_procs: schema.conint(gt = 0) = Field(
        1,
        description = "The number of MPI worker processes."
    )
    num_nodes: schema.conint(gt = 0) = Field(
        1,
        description = "The number of MPI nodes."
    )


class OpenFOAMResult(schema.BaseModel):
    """
    Represents an individual MPI openFOAM result.
    """
    wallclock_time: schema.confloat(ge = 0) = Field(
        ...,
        description = "The real time taken to complete the benchmark."
    )
    user_time: schema.confloat(ge = 0) = Field(
        ...,
        description = "The user time taken to complete the benchmark."
    )
    sys_time: schema.confloat(ge = 0) = Field(
        ...,
        description = "The sys time taken to complete the benchmark."
    )


class OpenFOAMStatus(base.BenchmarkStatus):
    """
    Represents the status of the iperf benchmark.
    """
    result: t.Optional[OpenFOAMResult] = Field(
        None,
        description = "The result of the benchmark."
    )
    master_pod: t.Optional[base.PodInfo] = Field(
        None,
        description = "Pod information for the MPI master pod."
    )
    worker_pods: schema.Dict[str, base.PodInfo] = Field(
        default_factory = dict,
        description = "Pod information for the worker pods, indexed by pod name."
    )


class OpenFOAM(
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
            "name": "Transport",
            "type": "string",
            "jsonPath": ".spec.transport",
        },
        {
            "name": "Problem Size",
            "type": "string",
            "jsonPath": ".spec.problemSize",
        },
        {
            "name": "Num Procs",
            "type": "integer",
            "jsonPath": ".spec.numProcs",
        },
        {
            "name": "Num Nodes",
            "type": "integer",
            "jsonPath": ".spec.numNodes",
        },
        {
            "name": "Status",
            "type": "string",
            "jsonPath": ".status.phase",
        },
        {
            "name": "Master IP",
            "type": "string",
            "jsonPath": ".status.masterPod.podIp",
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
            "name": "Wall time",
            "type": "number",
            "jsonPath": ".status.result.wallclockTime",
        },
    ]
):
    """
    Custom resource for running an iperf benchmark.
    """
    spec: OpenFOAMSpec = Field(
        ...,
        description = "The parameters for the benchmark."
    )
    status: OpenFOAMStatus = Field(
        default_factory = OpenFOAMStatus,
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
            pod_log = await fetch_pod_log()
            # Extract the time info from the pod log
            wallclock_time = None
            user_time = None
            sys_time = None
            for line in pod_log.splitlines():
                match = TIME_REGEX.match(line)
                if match is not None:
                    if match.group("type") == "real":
                        wallclock_time = match.group("time")
                    elif match.group("type") == "user":
                        user_time = match.group("time")
                    elif match.group("type") == "sys":
                        sys_time = match.group("time")
                    else:
                        raise PodLogFormatError("this is impossible")
            if wallclock_time is None or user_time is None or sys_time is None:
                raise PodLogFormatError("unable to extract timing information")
            self.status.result = OpenFOAMResult(
                wallclock_time = wallclock_time,
                user_time = user_time,
                sys_time = sys_time
            )

    def summarise(self):
        """
        Update the status of this benchmark with overall results.
        """
        if not self.status.result:
            raise PodResultsIncompleteError("master pod has not recorded a result yet")
