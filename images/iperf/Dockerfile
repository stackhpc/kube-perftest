#####
# Dockerfile for the iperf benchmarks
#####

FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get upgrade && \
    apt-get install -y "iperf" && \
    rm -rf /var/lib/apt/lists/*

EXPOSE 5001
