# kube-perftest  <!-- omit in toc -->

`kube-perftest` is a framework for building and running performance benchmarks for
[Kubernetes](https://kubernetes.io/) clusters.

- [Installation](#installation)
- [Benchmarks](#benchmarks)
  - [iperf](#iperf)
  - [Intel MPI Benchmarks (IMB) MPI1 PingPong](#intel-mpi-benchmarks-imb-mpi1-pingpong)
  - [OpenFOAM](#openfoam)
- [Benchmark set](#benchmark-set)

## Installation

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

## Benchmarks

Currently, the following benchmarks are supported:

### iperf

Runs the [iperf](https://en.wikipedia.org/wiki/Iperf) network performance tool to measure bandwidth
for a transfer between two pods.

Can be run using CNI or host networking, using a Kubernetes `Service` or connecting
directly to the server pod and using a configurable number of client streams.

```yaml
apiVersion: perftest.stackhpc.com/v1alpha1
kind: IPerf
metadata:
  name: iperf
spec:
  # Indicates whether to use the host network or the pod network
  hostNetwork: true
  # Indicates whether the client should access the server pod directly (false)
  # or via a Kubernetes service (true)
  serverService: false
  # The number of parallel streams to use
  streams: 8
  # The duration of the test
  duration: 30
```

### Intel MPI Benchmarks (IMB) MPI1 PingPong

Runs the
[IMB-MPI1 PingPong](https://www.intel.com/content/www/us/en/develop/documentation/imb-user-guide/top/mpi-1-benchmarks/single-transfer-benchmarks/pingpong-pingpongspecificsource-pingponganysource.html)
benchmark to measure the average round-trip time and bandwidth for MPI messages of different sizes
between two pods.

Currently uses MPI over TCP, initialised over SSH, and can be run using CNI or host networking.

```yaml
apiVersion: perftest.stackhpc.com/v1alpha1
kind: MPIPingPong
metadata:
  name: mpi-pingpong
spec:
  # Indicates whether to use the host network or the pod network
  hostNetwork: true
```

### OpenFOAM

This benchmark runs the
[3-D Lid Driven cavity flow benchmark](https://develop.openfoam.com/committees/hpc#3-d-lid-driven-cavity-flow)
from the OpenFOAM(https://www.openfoam.com/) benchmark suite.

Currently uses MPI over TCP, initialised over SSH, and can be run using CNI or host networking.

```yaml
apiVersion: perftest.stackhpc.com/v1alpha1
kind: OpenFOAM
metadata:
  name: openfoam
spec:
  # Indicates whether to use the host network or the pod network
  hostNetwork: false
  # The problem size to use (S, M, XL, XXL)
  problemSize: S
  # The number of MPI processes to use
  numProcs: 16
  # The number of MPI pods to launch
  numNodes: 8
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
  # Defines the permutations for the set
  # Each permutation is merged into the spec of the template
  permutations:
    # Permutations are calculated as a cross-product of the specified names and values
    product:
      hostNetwork: [true, false]
      serverService: [true, false]
      streams: [1, 2, 4, 8, 16, 32, 64]
    # A list of explicit permutations to include
    explicit:
      - hostNetwork: true
        serverService: false
        streams: 128
```
