# kube-perftest  <!-- omit in toc -->

`kube-perftest` is a framework for building and running performance benchmarks for
[Kubernetes](https://kubernetes.io/) clusters.

- [Installation](#installation)
- [Network selection](#network-selection)
- [Benchmark set](#benchmark-set)
- [Benchmarks](#benchmarks)
  - [iperf](#iperf)
  - [MPI PingPong](#mpi-pingpong)
  - [OpenFOAM](#openfoam)
  - [RDMA Bandwidth](#rdma-bandwidth)
  - [RDMA Latency](#rdma-latency)
  - [fio](#fio)
  - [PyTorch](#PyTorch)
- [Operator development](#operator-development)

## Installation

Requires a volcano.sh installation on the cluster, can be installed using

```sh
kubectl apply -f https://raw.githubusercontent.com/volcano-sh/volcano/master/installer/volcano-development.yaml
```

The `kube-perftest` operator can be installed using [Helm](https://helm.sh):

```sh
helm repo add kube-perftest https://stackhpc.github.io/kube-perftest
# Use the most recent published chart for the main branch
helm upgrade \
  kube-perftest-operator \
  kube-perftest/kube-perftest-operator \
  -i \
  --version ">=0.1.0-dev.0.main.0,<0.1.0-dev.0.main.99999999999"
```

For most use cases, no customisations to the Helm values will be necessary.

## Network selection

All the benchmarks are capable of running using the Kubernetes pod network or the host network
(using `hostNetwork: true` on the benchmark pods).

Benchmarks are also able to run on accelerated networks where available, using
[Multus](https://github.com/k8snetworkplumbingwg/multus-cni) for multiple CNIs and
[device plugins](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/device-plugins/)
to request network resources.

This allows benchmarks to levarage technologies such as
[SR-IOV](https://en.wikipedia.org/wiki/Single-root_input/output_virtualization)
(via the [SR-IOV network device plugin](https://github.com/k8snetworkplumbingwg/sriov-network-device-plugin)),
[macvlan](https://backreference.org/2014/03/20/some-notes-on-macvlanmacvtap/) (via the
[macvlan CNI plugin](https://www.cni.dev/plugins/current/main/macvlan/)) and
[RDMA](https://en.wikipedia.org/wiki/Remote_direct_memory_access)
(e.g. via the [RDMA shared device plugin](https://github.com/Mellanox/k8s-rdma-shared-dev-plugin)).

The networking is configured using the following properties of the benchmark `spec`:

```yaml
spec:
  # Indicates whether to use host networking or not
  # If true, networkName is not used
  hostNetwork: false
  # The name of a Multus network to use
  # Only used if hostNetwork is false
  # If not given, the Kubernetes pod network is used
  networkName: namespace/netname
  # The resources for benchmark pods
  resources:
    limits:
      # E.g. requesting a share of an RDMA device
      rdma/hca_shared_devices_a: 1
  # The MTU to set on the interface *inside* the container
  # If not given, the default MTU is used
  mtu: 9000
```

## Benchmark set

The `kube-perftest` operator provides a `BenchmarkSet` resource that can be used to run
the same benchmark over a sweep of parameters:

```yaml
apiVersion: perftest.stackhpc.com/v1alpha1
kind: BenchmarkSet
metadata:
  name: iperf
spec:
  # The template for the fixed parts of the benchmark
  template:
    apiVersion: perftest.stackhpc.com/v1alpha1
    kind: IPerf
    spec:
      duration: 30
  # The number of repetitions to run for each permutation
  # Defaults to 1 if not given
  repetitions: 1
  # Defines the permutations for the set
  # Each permutation is merged into the spec of the template
  # If not given, a single permutation consisting of the given template is used
  permutations:
    # Permutations are calculated as a cross-product of the specified names and values
    product:
      hostNetwork: [true, false]
      streams: [1, 2, 4, 8, 16, 32, 64]
    # A list of explicit permutations to include
    explicit:
      - hostNetwork: true
        streams: 128
```

## Benchmarks

Currently, the following benchmarks are supported:

### iperf

Runs the [iperf](https://en.wikipedia.org/wiki/Iperf) network performance tool to measure bandwidth
for a transfer between two pods.

```yaml
apiVersion: perftest.stackhpc.com/v1alpha1
kind: IPerf
metadata:
  name: iperf
spec:
  # The number of parallel streams to use
  streams: 8
  # The duration of the test
  duration: 30
```

### MPI PingPong

Runs the
[Intel MPI Benchmarks (IMB) MPI1 PingPong](https://www.intel.com/content/www/us/en/develop/documentation/imb-user-guide/top/mpi-1-benchmarks/single-transfer-benchmarks/pingpong-pingpongspecificsource-pingponganysource.html)
benchmark to measure the average round-trip time and bandwidth for MPI messages of different sizes
between two pods.

Uses [Open MPI](https://www.open-mpi.org/) initialised over SSH. The data plane can use TCP
or, hardware and network permitting, [RDMA](https://en.wikipedia.org/wiki/Remote_direct_memory_access)
via [UCX](https://openucx.org/).

```yaml
apiVersion: perftest.stackhpc.com/v1alpha1
kind: MPIPingPong
metadata:
  name: mpi-pingpong
spec:
  # The MPI transport to use - one of TCP, RDMA
  transport: TCP
  # Controls the maximum message length
  # Selected lengths, in bytes, will be 0, 1, 2, 4, 8, 16, ..., 2^maxlog
  # Defaults to 22 if not given, meaning the maximum message size will be 4MB
  maxlog: 22
```

### OpenFOAM

[OpenFOAM](https://www.openfoam.com/) is a toolbox for solving problems in
[computational fluid dynamics (CFD)](https://en.wikipedia.org/wiki/Computational_fluid_dynamics).
It is included here as an example of a "real world" workload.

This benchmark runs the
[3-D Lid Driven cavity flow benchmark](https://develop.openfoam.com/committees/hpc#3-d-lid-driven-cavity-flow)
from the OpenFOAM benchmark suite.

Uses [Open MPI](https://www.open-mpi.org/) initialised over SSH. The data plane can use TCP
or, hardware and network permitting, [RDMA](https://en.wikipedia.org/wiki/Remote_direct_memory_access)
via [UCX](https://openucx.org/).

```yaml
apiVersion: perftest.stackhpc.com/v1alpha1
kind: OpenFOAM
metadata:
  name: openfoam
spec:
  # The MPI transport to use - one of TCP, RDMA
  transport: TCP
  # The problem size to use - one of S, M, XL, XXL
  problemSize: S
  # The number of MPI processes to use
  numProcs: 16
  # The number of MPI pods to launch
  numNodes: 8
```

### RDMA Bandwidth

Runs the RDMA bandwidth benchmarks (i.e. `ib_{read,write}_bw`) from the
[perftest collection](https://github.com/linux-rdma/perftest).

This benchmark requires an RDMA-capable network to be specified.

```yaml
apiVersion: perftest.stackhpc.com/v1alpha1
kind: RDMABandwidth
metadata:
  name: rdma-bandwidth
spec:
  # The mode for the test - read or write
  mode: read
  # The number of iterations to do at each message size
  # Defaults to 1000 if not given
  iterations: 1000
  # The number of queue pairs to use
  # Defaults to 1 if not given
  # A higher number of queue pairs can help to spread traffic,
  # e.g. over NICs in a bond when using RoCE-LAG
  qps: 1
  # Extra arguments to be added to the command
  extraArgs:
    - --tclass=96
```

### RDMA Latency

Runs the RDMA latency benchmarks (i.e. `ib_{read,write}_lat`) from the
[perftest collection](https://github.com/linux-rdma/perftest).

This benchmark requires an RDMA-capable network to be specified.

```yaml
apiVersion: perftest.stackhpc.com/v1alpha1
kind: RDMALatency
metadata:
  name: rdma-latency
spec:
  # The mode for the test - read or write
  mode: read
  # The number of iterations to do at each message size
  # Defaults to 1000 if not given
  iterations: 1000
  # Extra arguments to be added to the command
  extraArgs:
    - --tclass=96
```

### fio

Runs filesystem performance benchmarking using [fio](https://fio.readthedocs.io) to
determine filesystem performance characteristics. All available `spec` options are
given below. Fio configration options match broadly with those defined in the fio
documentation.

Setting `.spec.volumeClaimTemplate` allows the provision of stable storage using 
`PersistentVolumes` provisioned by a [`PersistentVolume`](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
Provisioner.

When `spec.volumeClaimTemplate.accessModes` contains `ReadWriteMany`, this benchmark
will create a single `PersistentVolume` per `BenchmarkSet` iteration, and attach all
worker pods participting in the set (equal to `spec.numWorkers`) to the same volume.
Otherwise, a `PersistentVolume` per-pod is created and attached to each worker pod
participating in the benchmark.

```yaml
apiVersion: perftest.stackhpc.com/v1alpha1
kind: Fio
metadata:
  name: fio-filesystem
spec:
  # fio benchmark configuration options
  direct: 1
  iodepth: 8
  ioengine: libaio
  nrfiles: 1
  numJobs: 1
  bs: 1M
  rw: read
  percentageRandom: 100
  runtime: 10s
  rwmixread: 50
  size: 1G

  # kube-perftest benchmark configuration
  # options
  numWorkers: 1
  thread: false
  hostNetwork: false

  # PersistentVolume configuration options
  volumeClaimTemplate:
    accessModes:
      - ReadWriteOnce
    storageClassName: csi-cinder
    resources:
      requests:
        storage: 5Gi
```

### PyTorch

Runs machine learning model training and inference micro-benchmarks from the official 
PyTorch [benchmarks repo](https://github.com/pytorch/benchmark/) to compare performance
of CPU and GPU devices on synthetic input data. Running benchmarks on CUDA-capable
devices requires the [Nvidia GPU Operator](https://github.com/NVIDIA/gpu-operator) 
to be pre-installed on the target Kubernetes cluster.

The pre-built container image currently includes the `alexnet`, `resnet50` and 
`llama` (inference only) models - additional models from the 
[upstream repo list](https://github.com/pytorch/benchmark/tree/main/torchbenchmark/models)
may be added as needed in the future. (Adding a new model simply requires adding it to the list
in `images/pytorch-benchmark/Dockerfile` and updating the `PyTorchModel` enum in `pytorch.py`.)

```yaml
apiVersion: perftest.stackhpc.com/v1alpha1
kind: PyTorch
metadata:
  name: pytorch-test-gpu
spec:
  # The device to run the benchmark on ('cpu' or 'cuda')
  device: cuda
  # Name of model to benchmark
  model: alexnet
  # Either 'train' or 'eval'
  # (not all models support both)
  benchmarkType: eval
  # Batch size for generated input data
  inputBatchSize: 32
  resources:
    limits:
      nvidia.com/gpu: 2
```


## Operator development

```
# Install dependencies in a virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r python/requirements.txt
pip install -e python

# Set the default image tag
export KUBE_PERFTEST__DEFAULT_IMAGE_TAG=<dev branch name>

# Set the default image pull policy
export KUBE_PERFTEST__DEFAULT_IMAGE_PULL_POLICY=Always

# Run the operator
kopf run -m perftest.operator -A
```
