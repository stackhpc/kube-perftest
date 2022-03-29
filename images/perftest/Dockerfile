FROM debian:latest

ARG PERFTEST_VERSION=4.4+0.37-1
RUN apt-get update && \
    apt-get install -y "perftest=$PERFTEST_VERSION" && \
    rm -rf /var/lib/apt/lists/*
