FROM debian:latest

RUN apt-get update && \
    apt-get install -y iperf3 && \
    rm -rf /var/lib/apt/lists/*

EXPOSE 5201
ENTRYPOINT ["iperf3"]
