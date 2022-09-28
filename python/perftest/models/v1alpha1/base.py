import datetime
import ipaddress
import typing as t

from pydantic import Field, constr

from kube_custom_resource import CustomResource, schema

from ...template import Loader


class ImagePullPolicy(str, schema.Enum):
    """
    Enumeration of the possible pull policies.
    """
    ALWAYS = "Always"
    IF_NOT_PRESENT = "IfNotPresent"
    NEVER = "Never"


class ContainerResources(schema.BaseModel):
    """
    Model for specifying container resources.
    """
    requests: schema.Dict[str, t.Any] = Field(
        default_factory = dict,
        description = "The resource requests for the pod."
    )
    limits: schema.Dict[str, t.Any] = Field(
        default_factory = dict,
        description = "The resource limits for the pod."
    )


class BenchmarkPhase(str, schema.Enum):
    """
    Enumeration of possible phases for a benchmark.
    """
    # Indicates that the state of the benchmark is not known
    UNKNOWN = "Unknown"
    # Indicates that the benchmark is being prepared
    PREPARING = "Preparing"
    # Indicates that the benchmark is waiting to be scheduled
    PENDING = "Pending"
    # Indicates that the benchmark has been aborted and is waiting for cleanup
    ABORTING = "Aborting"
    # Indicates that the benchmark has been aborted
    ABORTED = "Aborted"
    # Indicates that minimum requested number of pods for the benchmark are running
    RUNNING = "Running"
    # Indicates that the benchmark is waiting for pods to be recreated
    RESTARTING = "Restarting"
    # Indicates that the benchmark has completed successfully and is waiting for cleanup
    COMPLETING = "Completing"
    # Indicates that cleanup has succeeded for the benchmark and it is producing a result
    SUMMARISING = "Summarising"
    # Indicates that the benchmark has completed successfully
    COMPLETED = "Completed"
    # Indicates that the benchmark finished unexpectedly and is waiting for cleanup
    TERMINATING = "Terminating"
    # Indicates that the benchmark finished unexpectedly, e.g. in response to an event
    TERMINATED = "Terminated"
    # Indicates that the benchmark reached the maximum number of retries without completing
    FAILED = "Failed"


class ResourceRef(schema.BaseModel):
    """
    Reference to a resource that is part of a benchmark.
    """
    api_version: constr(min_length = 1) = Field(
        ...,
        description = "The API version of the resource."
    )
    kind: constr(min_length = 1) = Field(
        ...,
        description = "The kind of the resource."
    )
    name: constr(min_length = 1) = Field(
        ...,
        description = "The name of the resource."
    )


class PodInfo(schema.BaseModel):
    """
    Model for basic information about a pod.
    """
    pod_ip: ipaddress.IPv4Address = Field(
        ...,
        description = "The IP of the pod."
    )
    node_name: constr(min_length = 1) = Field(
        ...,
        description = "The name of the node that the pod was scheduled on."
    )
    node_ip: ipaddress.IPv4Address = Field(
        ...,
        description = "The IP of the node that the pod was scheduled on."
    )

    @classmethod
    def from_pod(cls, pod: t.Dict[str, t.Any]) -> 'PodInfo':
        """
        Returns a new pod info object from the given pod.
        """
        return cls(
            pod_ip = pod["status"]["podIP"],
            node_name = pod["spec"]["nodeName"],
            node_ip = pod["status"]["hostIP"]
        )


class BenchmarkStatus(schema.BaseModel):
    """
    Base class for benchmark statuses.
    """
    phase: BenchmarkPhase = Field(
        BenchmarkPhase.UNKNOWN,
        description = "The phase of the benchmark."
    )
    priority_class_name: t.Optional[constr(min_length = 1)] = Field(
        None,
        description = "The name of the priority class for the benchmark."
    )
    managed_resources: t.List[ResourceRef] = Field(
        default_factory = list,
        description = "List of references to the managed resources for this benchmark."
    )
    started_at: t.Optional[datetime.datetime] = Field(
        None,
        description = "The time at which the benchmark started."
    )
    finished_at: t.Optional[datetime.datetime] = Field(
        None,
        description = "The time at which the benchmark finished."
    )


class Benchmark(CustomResource, abstract = True):
    """
    Base class for benchmark resources.
    """
    status: BenchmarkStatus = Field(
        default_factory = BenchmarkStatus,
        description = "The status of the benchmark."
    )

    def get_template(self) -> str:
        """
        Returns the name of the template to use for this benchmark.
        """
        return f"{self._meta.singular_name}.yaml.j2"

    def get_resources(self, template_loader: Loader) -> t.Iterable[t.Dict[str, t.Any]]:
        """
        Returns the resources to create for this benchmark.
        """
        # By default, this just renders a YAML template
        return template_loader.yaml_template_all(self.get_template(), benchmark = self)

    def job_modified(self, job: t.Dict[str, t.Any]):
        """
        Update the status of this benchmark to reflect a modification to the Volcano job.
        """
        # By default, update the benchmark phase to match the job
        # The benchmark phase matches the Volcano job phase until it reaches "Completed"
        # At that point, the benchmark goes into a Summarising phase, which triggers the
        # calculation of the overall result
        job_phase = job.get("status", {}).get("state", {}).get("phase", "Unknown")
        if job_phase == "Completed":
            self.status.phase = BenchmarkPhase.SUMMARISING
        else:
            self.status.phase = BenchmarkPhase(job_phase)

    async def pod_modified(
        self,
        pod: t.Dict[str, t.Any],
        fetch_pod_log: t.Callable[[], t.Awaitable[str]]
    ):
        """
        Update the status of this benchmark to reflect a modification to one of its pods.

        Receives the pod instance and an async function that can be called to get the pod log.
        """
        raise NotImplementedError

    def summarise(self):
        """
        Update the status of this benchmark with overall results.
        """
        raise NotImplementedError
