FROM ubuntu:20.04

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get install -y \
    ssh \
    wget \
    software-properties-common \
    git \
    time \
    rsync && \
    rm -rf /var/lib/apt/lists/*

RUN wget -O /etc/apt/trusted.gpg.d/openfoam.asc https://dl.openfoam.org/gpg.key
RUN add-apt-repository http://dl.openfoam.org/ubuntu

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get install -y openfoam10 openmpi-bin && \
    rm -rf /var/lib/apt/lists/*

RUN ln -sf /opt/openfoam10/etc/bashrc /root/.bashrc

RUN git clone https://develop.openfoam.com/committees/hpc.git /opt/hpc

COPY ./scripts/* /usr/local/bin/