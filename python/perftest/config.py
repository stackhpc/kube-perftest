import enum
import typing as t

from pydantic import Field, validator, constr

from configomatic import Configuration as BaseConfiguration, LoggingConfiguration


class ImagePullPolicy(str, enum.Enum):
    """
    Enumeration of the possible pull policies.
    """
    ALWAYS = "Always"
    IF_NOT_PRESENT = "IfNotPresent"
    NEVER = "Never"


DEFAULT_HOSTS = """
127.0.0.1  localhost
::1        localhost ip6-localhost ip6-loopback
"""


class Configuration(BaseConfiguration):
    """
    Top-level configuration model.
    """
    class Config:
        default_path = "/etc/kube-perftest/config.yaml"
        path_env_var = "KUBE_PERFTEST_CONFIG"
        env_prefix = "KUBE_PERFTEST"

    #: The logging configuration
    logging: LoggingConfiguration = Field(default_factory = LoggingConfiguration)

    #: The API group of the cluster CRDs
    api_group: constr(min_length = 1) = "perftest.stackhpc.com"
    #: A list of categories to place CRDs into
    crd_categories: t.List[constr(min_length = 1)] = Field(
        default_factory = lambda: ["perftest"]
    )

    #: The field manager name to use for server-side apply
    easykube_field_manager: constr(min_length = 1) = "kube-perftest-operator"

    #: The default image prefix to use for benchmark images
    default_image_prefix: constr(min_length = 1) = "ghcr.io/stackhpc/kube-perftest-"
    #: The default tag to use for benchmark images
    #: The chart will set this to the tag that matches the operator image
    default_image_tag: constr(min_length = 1) = "latest"
    #: The image pull policy to use for benchmarks
    default_image_pull_policy: ImagePullPolicy = ImagePullPolicy.IF_NOT_PRESENT

    #: The name of the scheduler to use
    #:   Pod preemption, especially when combined with (anti-)affinity appears to be at
    #:   best difficult to configure (at worst broken) in the Volcano scheduler, so we
    #:   use the default scheduler
    #:   This means we don't benefit from resource-based gang scheduling, but the
    #:   pod preemption works which means pods get scheduled simultaneously properly
    #:   We still also benefit from Volcano's handling of job events
    scheduler_name: constr(min_length = 1) = "default-scheduler"
    #: The name of the Volcano queue to use
    queue_name: constr(min_length = 1) = "default"

    #: Label specifying the kind of the benchmark that a resource belongs to
    kind_label: constr(min_length = 1) = None
    #: Label specifying the namespace of the benchmark that a resource belongs to
    namespace_label: constr(min_length = 1) = None
    #: Label specifying the name of the benchmark that a resource belongs to
    name_label: constr(min_length = 1) = None
    #: Label specifying the component of the benchmark that a resource belongs to
    component_label: constr(min_length = 1) = None

    #: Label indicating that a configmap should be populated with hosts from a service
    hosts_from_label: constr(min_length = 1) = None
    #: The default hosts for the generated hosts files
    default_hosts: constr(min_length = 1) = DEFAULT_HOSTS.strip()

    #: The default priority when there are no existing priority classes
    #: By default, we use negative priorities so that jobs will not preempt other pods
    initial_priority: int = -1
    #: The prefix to use for generating resource names
    resource_prefix: constr(min_length = 1) = "kube-perftest-"

    @validator("kind_label", pre = True, always = True)
    def default_kind_label(cls, v, *, values, **kwargs):
        return v or f"{values['api_group']}/benchmark-kind"

    @validator("namespace_label", pre = True, always = True)
    def default_namespace_label(cls, v, *, values, **kwargs):
        return v or f"{values['api_group']}/benchmark-namespace"

    @validator("name_label", pre = True, always = True)
    def default_name_label(cls, v, *, values, **kwargs):
        return v or f"{values['api_group']}/benchmark-name"

    @validator("component_label", pre = True, always = True)
    def default_component_label(cls, v, *, values, **kwargs):
        return v or f"{values['api_group']}/benchmark-component"

    @validator("hosts_from_label", pre = True, always = True)
    def default_hosts_from_label(cls, v, *, values, **kwargs):
        return v or f"{values['api_group']}/hosts-from"


settings = Configuration()
