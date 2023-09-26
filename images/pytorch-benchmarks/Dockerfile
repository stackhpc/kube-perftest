FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime

RUN apt update && apt install -y git time
RUN git clone https://github.com/pytorch/benchmark
WORKDIR /workspace/benchmark
# Pin pytorch-benchmark repo version
RUN git reset --hard 6fef32ddaf93a63088b97eb27620fb57ef247521
# Add other benchmarks here?
RUN python install.py alexnet resnet50 llama

# PyTorch install.py pins numpy=1.21.2 but
# this breaks numba so update both here
RUN pip install -U numpy numba