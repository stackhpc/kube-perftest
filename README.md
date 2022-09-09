# kube-perftest

`kube-perftest` is a framework for building and running performance benchmarks for
[Kubernetes](https://kubernetes.io/) clusters.

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
directly to the pod for the server and using a configurable number of client streams.

### Intel MPI Benchmarks (IMB) MPI1 PingPong

Runs the
[IMB-MPI1 PingPong](https://www.intel.com/content/www/us/en/develop/documentation/imb-user-guide/top/mpi-1-benchmarks/single-transfer-benchmarks/pingpong-pingpongspecificsource-pingponganysource.html)
benchmark to measure the average round-trip time and bandwidth for MPI messages of different sizes
between two pods.

Currently uses SSH over TCP, initialised over SSH, and can be run using CNI or host networking.
