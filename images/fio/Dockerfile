#####
# Dockerfile for the fio benchmarks
#####

FROM debian:bookworm-slim

ARG FIO_VERSION=3.33-3
RUN apt-get update && \
    apt-get install -y tini fio=${FIO_VERSION} && \
    rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["tini", "-g", "--"]
# Install the setup and run scripts
COPY scripts/* /usr/local/bin/