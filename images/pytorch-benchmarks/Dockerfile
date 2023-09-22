FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime

RUN apt update && apt install -y git
# TODO: Checkout certain commit here
RUN git clone https://github.com/pytorch/benchmark
WORKDIR /workspace/benchmark
# Add other benchmarks here?
RUN python install.py alexnet resnet50 llama

# PyTorch install.py pins numpy=1.21.2 but this breaks numba so update both here
RUN pip install -U numpy numba

COPY run-benchmark.sh /usr/local/bin/