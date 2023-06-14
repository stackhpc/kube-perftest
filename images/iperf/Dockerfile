#####
# Dockerfile for the iperf benchmarks
#####


FROM debian:bookworm-slim

ARG IPERF_VERSION=2.1.8+dfsg-1
RUN apt-get update && \
    apt-get install -y "iperf=$IPERF_VERSION" && \
    rm -rf /var/lib/apt/lists/*

EXPOSE 5001
