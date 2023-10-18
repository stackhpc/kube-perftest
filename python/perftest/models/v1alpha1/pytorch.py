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

# List of models here should match list in images/pytorch-benchmark/Dockerfile
class PyTorchModel(str, schema.Enum):
    """
    Enumeration of available models for benchmarking.
    """
    ALEXNET = "alexnet"
    RESNET50 = "resnet50"
    LLAMA = "llama"
    
class PyTorchBenchmarkType(str, schema.Enum):
    """
    Enumeration of model processes available to benchmark.
    """
    TRAIN = "train"
    EVAL = "eval"


class PyTorchSpec(base.BenchmarkSpec):
    """
    Defines the parameters for the Fio benchmark.
    """
    image: constr(min_length = 1) = Field(
        f"{settings.default_image_prefix}pytorch-benchmarks:{settings.default_image_tag}",
        description = "The image to use for the benchmark."
    )
    image_pull_policy: base.ImagePullPolicy = Field(
        base.ImagePullPolicy.IF_NOT_PRESENT,
        description = "The pull policy for the image."
    )
    # PyTorch benchmark config options
    device: Device = Field(
        Device.CPU,
        description = (
            "The device to run the ML workload."
            "If device is 'cuda' then you must also make a request for GPU resources by"
            "adding a 'nvidia.com/gpu: <gpu-count>' field to benchmark.spec.resources.limits"
        )
    )
    model: PyTorchModel = Field(
        description = "The ML model to benchmark."
    )
    benchmark_type: PyTorchBenchmarkType = Field(
        PyTorchBenchmarkType.EVAL,
        description = "Whether to benchmark the training or inference (eval) process."
    )
    input_batch_size: conint(multiple_of=2, ge=2) = Field(
        64,
        description = "The batch size for the generated model input data.",
    )
            

class PyTorchResult(schema.BaseModel):
    """
    Represents an individual PyTorch benchmark result.
    
    Some notes on the inner workings of the pytorch benchmark script:
    - Currently only runs one batch for benchmark so 'time per batch' in pytorch output == total time.
      (This may change in future since 'per batch' suffix was added to output text very recently.)
      https://github.com/pytorch/benchmark/blob/6fef32ddaf93a63088b97eb27620fb57ef247521/run.py#L468
    - CPU 'wall time' reported by pytorch is significantly shorter than reported by GNU `time` command.
      It's not clear what is taking up this extra time outwith the actual model invocation (downloading
      model weights and generating random in-memory input data shouldn't take long at all).
    """
    pytorch_time: schema.confloat(ge = 0) = Field(
        ...,
        description = "The CPU wall time (in seconds) as reported by the pytorch benchmark script."
    )
    peak_cpu_memory: schema.confloat(ge = 0) = Field(
        ...,
        description = "The peak CPU memory usage (in GB) reported by the pytorch benchmark script."
    )
    gpu_time: t.Optional[schema.confloat(ge = 0)] = Field(
        None, # Default to zero for clearer reporting on cpu-only runs
        description = "The GPU wall time (in seconds) reported by the pytorch benchmark script."
    )
    peak_gpu_memory: t.Optional[schema.confloat(ge = 0)] = Field(
        None, # Default to zero for clearer reporting on cpu-only runs
        description = "The peak GPU memory usage (in GB) reported by the pytorch benchmark script."
    )
    gnu_time: GnuTimeResult = Field(
        description = "A container for the output of the `time` command which wraps the benchmark execution script."
    )
    

class PyTorchStatus(base.BenchmarkStatus):
    """
    Represents the status of the PyTorch benchmark.
    """
    gpu_count: conint(ge=0) = Field(
        None,
        description = "The number of gpus used in this benchmark"
    )
    result: t.Optional[PyTorchResult] = Field(
        None,
        description = "The result of the benchmark."
    )
    wall_time_result: schema.confloat(ge = 0) = Field(
        None,
        description = (
            "The wall time (in seconds) reported by the GNU time wrapper."
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


class PyTorch(
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
            "name": "Wall Time (s)",
            "type": "number",
            "jsonPath": ".status.wallTimeResult",
        },
        {
            "name": "GPU Time (s)",
            "type": "number",
            "jsonPath": ".status.gpuTimeResult",
        },
    ]
):
    """
    Custom resource for running an PyTorch benchmark.
    """
    spec: PyTorchSpec = Field(
        ...,
        description = "The parameters for the benchmark."
    )
    status: PyTorchStatus = Field(
        default_factory = PyTorchStatus,
        description = "The status of the benchmark."
    )

    async def pod_modified(
        self,
        pod: t.Dict[str, t.Any],
        fetch_pod_log: t.Callable[[], t.Awaitable[str]]
    ):  
        # Parse GPU count from resources to display in status
        if self.spec.resources:
            if self.spec.resources.limits:
                if 'nvidia.com/gpu' in self.spec.resources.limits.keys():
                    self.status.gpu_count = self.spec.resources.limits['nvidia.com/gpu']
        else:
            self.status.gpu_count = 0

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
        cpu_time_match = PYTORCH_CPU_TIME_REGEX.search(self.status.client_log)
        cpu_time = cpu_time_match.group('cpu_time')
        cpu_time_units = cpu_time_match.group('cpu_time_units')
        cpu_memory_match = PYTORCH_CPU_MEMORY_REGEX.search(self.status.client_log)
        cpu_peak_memory = cpu_memory_match.group('cpu_memory')
        cpu_peak_memory_units = cpu_memory_match.group('cpu_mem_units')

        if cpu_time_units != "milliseconds" or cpu_peak_memory_units != "GB":
            raise PodLogFormatError(
                "results output in unexpected units - expected 'milliseconds' and 'GB'"
                "(it's possible that results formatting has changed in upstream pytorch-benchmarks)"
            )

        if self.spec.device != "cpu":
            # Parse GPU results
            gpu_time_match = PYTORCH_GPU_TIME_REGEX.search(self.status.client_log)
            gpu_time = gpu_time_match.group('gpu_time')
            gpu_time_units = gpu_time_match.group('gpu_time_units')
            gpu_memory_match = PYTORCH_GPU_MEMORY_REGEX.search(self.status.client_log)
            gpu_peak_memory = gpu_memory_match.group('gpu_memory')
            gpu_peak_memory_units = gpu_memory_match.group('gpu_mem_units')
            if gpu_time_units != "milliseconds" or gpu_peak_memory_units != "GB":
                raise PodLogFormatError(
                    "results output in unexpected units - expected 'milliseconds' and 'GB'"
                    "(it's possible that results formatting has changed in upstream pytorch-benchmarks)"
                )
            # Convert times to seconds to match GNU time output    
            gpu_time = float(gpu_time) / 1000
        else:
            gpu_time, gpu_peak_memory = None, None
        
        # Parse the GNU time wrapper output
        gnu_time_result = GnuTimeResult.parse(self.status.client_log)
        
        # Convert times to seconds to match GNU time output
        self.status.result = PyTorchResult(
            pytorch_time = float(cpu_time) / 1000,
            peak_cpu_memory = cpu_peak_memory,
            gpu_time = gpu_time,
            peak_gpu_memory = gpu_peak_memory,
            gnu_time = gnu_time_result,
        )

        # Format results nicely for printing
        self.status.wall_time_result = float(f"{self.status.result.gnu_time.wall_time_secs:.3g}")
        if self.status.result.gpu_time:
            self.status.gpu_time_result = float(f"{self.status.result.gpu_time:.3g}")
