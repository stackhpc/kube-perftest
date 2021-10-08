FROM debian:latest

RUN apt-get update && \
    apt-get install -y fio && \
    rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["fio"]
