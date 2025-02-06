FROM pytorch/pytorch:2.6.0-cuda11.8-cudnn9-runtime

RUN apt update && apt install -y git time
RUN git clone https://github.com/pytorch/benchmark
WORKDIR /workspace/benchmark
# Pin pytorch-benchmark repo version
RUN git reset --hard a22a2a8309d513c66df995ae27ee48c954b49f66
# List of models here should match PytorchModel enum
# in python/perftest/pytorch.py
RUN python install.py alexnet resnet50 llama

# PyTorch install.py pins numpy=1.21.2 but
# this breaks numba so update both here
RUN pip install -U numpy numba
