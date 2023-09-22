FROM nvcr.io/nvidia/pytorch:22.12-py3

# RUN pip install -U pip
# RUN pip install torchvision torchaudio
RUN pip uninstall torch -y && pip install --no-cache torch torchvision torchaudio

# RUN git clone https://github.com/pytorch/benchmark
# WORKDIR /workspace/benchmark
# # Add other benchmarks here?
# RUN python install.py alexnet resnet50 llama

# COPY run-benchmark.sh /usr/local/bin/