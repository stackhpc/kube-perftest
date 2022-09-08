FROM debian:latest

# Install iperf, but also netcat for testing when the server is available
ARG IPERF_VERSION=2.0.14a+dfsg1-1
RUN apt-get update && \
    apt-get install -y netcat "iperf=$IPERF_VERSION" && \
    rm -rf /var/lib/apt/lists/*

EXPOSE 5001
ENTRYPOINT ["iperf"]
