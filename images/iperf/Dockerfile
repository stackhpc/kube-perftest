FROM debian:latest

ARG IPERF_VERSION=3.9-1
RUN apt-get update && \
    apt-get install -y "iperf3=$IPERF_VERSION" && \
    rm -rf /var/lib/apt/lists/*

EXPOSE 5201
ENTRYPOINT ["iperf3"]
