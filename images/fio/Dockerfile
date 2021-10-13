FROM debian:latest

ARG FIO_VERSION=3.25-2
RUN apt-get update && \
    apt-get install -y tini "fio=$FIO_VERSION" && \
    rm -rf /var/lib/apt/lists/*

# Install the setup and run scripts
COPY fio-prepare.sh  /usr/local/bin/fio-prepare
COPY fio-run.sh      /usr/local/bin/fio-run

ENTRYPOINT ["tini", "-g", "--"]
CMD ["fio-run"]
