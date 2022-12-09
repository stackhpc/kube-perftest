ARG FEDORA_VERSION=37
FROM fedora:${FEDORA_VERSION}

ARG FIO_VERSION=3.30-2
ARG FEDORA_VERSION
RUN dnf install -y fio-${FIO_VERSION}.fc${FEDORA_VERSION} && \
    dnf clean all && \
    rm -rf /var/cache/dnf

# Install the setup and run scripts
COPY scripts/* /usr/local/bin/