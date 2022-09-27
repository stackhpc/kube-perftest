FROM ubuntu:22.04

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && \
    apt-get install -y \
      curl \
      git \
      openmpi-bin \
      openssh-client \
      openssh-server \
      rsync \
      software-properties-common \
      time \
      ucx-utils && \
    rm -rf /var/lib/apt/lists/*

ARG OPENFOAM_VERSION=20220831
RUN curl -fsSLo /etc/apt/trusted.gpg.d/openfoam.asc https://dl.openfoam.org/gpg.key && \
    add-apt-repository http://dl.openfoam.org/ubuntu && \
    apt-get update && \
    apt-get install -y "openfoam10=$OPENFOAM_VERSION" && \
    rm -rf /var/lib/apt/lists/*

RUN git clone https://develop.openfoam.com/committees/hpc.git /opt/hpc

COPY ./scripts/* /usr/local/bin/
