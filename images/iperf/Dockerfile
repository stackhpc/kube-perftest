FROM debian:latest

ARG IPERF_VERSION=2.0.14a+dfsg1-1
RUN apt-get update && \
    apt-get install -y "iperf=$IPERF_VERSION" && \
    rm -rf /var/lib/apt/lists/*

EXPOSE 5001
ENTRYPOINT ["iperf"]
