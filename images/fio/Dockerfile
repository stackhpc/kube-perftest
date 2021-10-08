FROM debian:latest

ARG FIO_VERSION=3.25-2
RUN apt-get update && \
    apt-get install -y tini "fio=$FIO_VERSION" && \
    rm -rf /var/lib/apt/lists/*

# Install the run script
COPY fio-run.sh /usr/local/bin/fio-run

ENTRYPOINT ["tini", "-g", "--"]
CMD ["fio-run"]
