import re
import datetime as dt
import typing as t

from pydantic import Field, constr, conint

from kube_custom_resource import schema

from ...config import settings
from ...errors import PodLogFormatError, PodResultsIncompleteError
from ...utils import GnuTimeResult

from . import base

# If results output format changes in future pytorch-benchmark versions
# check https://github.com/pytorch/benchmark/blob/main/run.py for changes
PYTORCH_CPU_TIME_REGEX = re.compile(r"CPU Wall Time per batch:\s+(?P<cpu_time>\d+\.\d+)\s*(?P<cpu_time_units>\w+)")
PYTORCH_CPU_MEMORY_REGEX = re.compile(r"CPU Peak Memory:\s+(?P<cpu_memory>\d+\.\d+)\s*(?P<cpu_mem_units>\w+)")
PYTORCH_GPU_TIME_REGEX = re.compile(r"GPU Time per batch:\s+(?P<gpu_time>\d+\.\d+)\s*(?P<gpu_time_units>\w+)")
PYTORCH_GPU_MEMORY_REGEX = re.compile(r"GPU \d+ Peak Memory:\s+(?P<gpu_memory>\d+\.\d+)\s*(?P<gpu_mem_units>\w+)")


class Device(str, schema.Enum):
    """
    Enumeration of supported computation devices.
    """
    CPU = "cpu"
    CUDA = "cuda"

# NOTE: List of models here should match list in images/pytorch-benchmark/Dockerfile
class PytorchModel(str, schema.Enum):
    """
    Eumeration available models for benchmarking.
    """
    ALEXNET = "alexnet"
    RESNET50 = "resnet50"
    LLAMA = "llama"
    
class PytorchBenchmarkType(str, schema.Enum):
    """
    Enumeration of model processes available to benchmark.
    """
    TRAIN = "train"
    EVAL = "eval"

class PytorchSpec(base.BenchmarkSpec):
    """
    Defines the parameters for the Fio benchmark.
    """
    # image: constr(min_length = 1) = Field(
    #     f"{settings.default_image_prefix}fio:{settings.default_image_tag}",
    #     description = "The image to use for the benchmark."
    # )
    # image_pull_policy: base.ImagePullPolicy = Field(
    #     base.ImagePullPolicy.IF_NOT_PRESENT,
    #     description = "The pull policy for the image."
    # )
    # Pytorch benchmark config options
    device: Device = Field(
        Device.CPU,
        description = "The device to run the ML workload."
    )
    model: PytorchModel = Field(
        description = "The ML model to benchmark."
    )
    benchmark_type: PytorchBenchmarkType = Field(
        PytorchBenchmarkType.EVAL,
        description = "Whether to benchmark the training or inference (eval) process."
    )
    input_batch_size: conint(multiple_of=2, ge=2) = Field(
        64,
        description = "The batch size for the generated model input data.",
    )
    gpu_count: t.Optional[conint(ge=1)] = Field(
        None,
        description = "Number of GPUs to request for the benchmark run. Defaults to 0 for device = cpu and 1 for device = cuda."
    )            
        

class PytorchResult(schema.BaseModel):
    """
    Represents an individual Pytorch benchmark result.
    """
    cpu_wall_time: schema.confloat(ge = 0) = Field(
        ...,
        description = "The CPU wall time (in seconds) per batch as reported by the pytorch benchmark script."
    )
    peak_cpu_memory: schema.confloat(ge = 0) = Field(
        ...,
        description = "The peak CPU memory usage (in GB) reported by the pytorch benchmark script."
    )
    gpu_wall_time: t.Optional[schema.confloat(ge = 0)] = Field(
        None, # Default to zero for clearer reporting on cpu-only runs
        description = "The GPU wall time (in seconds) reported by the pytorch benchmark script."
    )
    peak_gpu_memory: t.Optional[schema.confloat(ge = 0)] = Field(
        None, # Default to zero for clearer reporting on cpu-only runs
        description = "The peak GPU memory usage (in GB) reported by the pytorch benchmark script."
    )
    gnu_time: GnuTimeResult = Field(
        description = "The output of the `time` command which wraps the benchmark execution script."
    )
    

class PytorchStatus(base.BenchmarkStatus):
    """
    Represents the status of the Pytorch benchmark.
    """
    gpu_count: conint(ge=0) = Field(
        None,
        description = "The number of gpus used in this benchmark"
    )
    result: t.Optional[PytorchResult] = Field(
        None,
        description = "The result of the benchmark."
    )
    cpu_time_result: schema.confloat(ge = 0) = Field(
        None,
        description = (
            "The CPU wall time (in seconds) reported by the pytorch benchmark script."
            "Used as a headline result."
        )
    )
    gpu_time_result: schema.confloat(ge = 0) = Field(
        None,
        description = (
            "The GPU wall time (in seconds) reported by the pytorch benchmark script."
            "Used as a headline result."
        )
    )
    worker_pod: t.Optional[base.PodInfo] = Field(
        None,
        description = "Pod information for the pod running the benchmark."
    )
    client_log: t.Optional[constr(min_length = 1)] = Field(
        None,
        description = "The raw pod log of the client pod."
    )


class Pytorch(
    base.Benchmark,
    subresources = {"status": {}},
    printer_columns = [
        {
            "name": "Model",
            "type": "string",
            "jsonPath": ".spec.model",
        },
        {
            "name": "Benchmark Type",
            "type": "string",
            "jsonPath": ".spec.benchmarkType",
        },
        {
            "name": "Device",
            "type": "string",
            "jsonPath": ".spec.device",
        },
        {
            "name": "GPUs",
            "type": "integer",
            "jsonPath": ".status.gpuCount",
        },
        {
            "name": "Batch Size",
            "type": "integer",
            "jsonPath": ".spec.inputBatchSize",
        },
        {
            "name": "Status",
            "type": "string",
            "jsonPath": ".status.phase",
        },        
        {
            "name": "CPU Wall Time (s)",
            "type": "number",
            "jsonPath": ".status.cpuTimeResult",
        },
        {
            "name": "GPU Time (s)",
            "type": "number",
            "jsonPath": ".status.gpuTimeResult",
        },
    ]
):
    """
    Custom resource for running an Pytorch benchmark.
    """
    spec: PytorchSpec = Field(
        ...,
        description = "The parameters for the benchmark."
    )
    status: PytorchStatus = Field(
        default_factory = PytorchStatus,
        description = "The status of the benchmark."
    )

    async def pod_modified(
        self,
        pod: t.Dict[str, t.Any],
        fetch_pod_log: t.Callable[[], t.Awaitable[str]]
    ):  
        # Set default GPU count if none given in spec
        gpu_count = pod.get("status", {}).get("gpuCount")
        if gpu_count is None:
            self.status.gpu_count = (0 if self.spec.device == "cpu" else 1)

        pod_phase = pod.get("status", {}).get("phase", "Unknown")
        if pod_phase == "Running":
            self.status.worker_pod = base.PodInfo.from_pod(pod)
        elif pod_phase == "Succeeded":
            self.status.client_log = await fetch_pod_log()

    def summarise(self):
        # If the client log has not yet been recorded, bail
        if not self.status.client_log:
            raise PodResultsIncompleteError("Pod has not recorded a result yet")

        # Parse job output here
        cpu_time = PYTORCH_CPU_TIME_REGEX.search(self.status.client_log).group('cpu_time')
        cpu_time_units = PYTORCH_CPU_TIME_REGEX.search(self.status.client_log).group('cpu_time_units')
        cpu_peak_memory = PYTORCH_CPU_MEMORY_REGEX.search(self.status.client_log).group('cpu_memory')
        cpu_peak_memory_units = PYTORCH_CPU_MEMORY_REGEX.search(self.status.client_log).group('cpu_mem_units')

        if cpu_time_units != "milliseconds" or cpu_peak_memory_units != "GB":
            raise PodLogFormatError(
                "results output in unexpected units"
                "(it's possible that results formatting has changed in upstream pytorch-benchmarks)"
            )

        if self.spec.device != "cpu":
            # Parse GPU results
            gpu_time = PYTORCH_GPU_TIME_REGEX.search(self.status.client_log).group('gpu_time')
            gpu_peak_memory = PYTORCH_GPU_MEMORY_REGEX.search(self.status.client_log).group('gpu_memory')
            gpu_time_units = PYTORCH_GPU_TIME_REGEX.search(self.status.client_log).group('gpu_time_units')
            gpu_peak_memory_units = PYTORCH_GPU_MEMORY_REGEX.search(self.status.client_log).group('gpu_mem_units')
            if gpu_time_units != "milliseconds" or gpu_peak_memory_units != "GB":
                raise PodLogFormatError(
                    "results output in unexpected units"
                    "(it's possible that results formatting has changed in upstream pytorch-benchmarks)"
                )
            # Convert times to seconds to match GNU time output    
            gpu_time = float(gpu_time) / 1000
        else:
            gpu_time, gpu_peak_memory = None, None
        
        # Parse the GNU time wrapper output
        gnu_time_result = GnuTimeResult.parse(self.status.client_log)
        
        # Convert times to seconds to match GNU time output
        self.status.result = PytorchResult(
            cpu_wall_time = float(cpu_time) / 1000,
            peak_cpu_memory = cpu_peak_memory,
            gpu_wall_time = gpu_time,
            peak_gpu_memory = gpu_peak_memory,
            gnu_time = gnu_time_result,
        )

        # Format results nicely for printing
        self.status.cpu_time_result = float(f"{self.status.result.cpu_wall_time:.3g}")
        if self.status.result.gpu_wall_time:
            self.status.gpu_time_result = float(f"{self.status.result.gpu_wall_time:.3g}")
