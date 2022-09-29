FROM debian:bullseye-slim


RUN apt-get update && \
    apt-get install -y iproute2 netcat && \
    rm -rf /var/lib/apt/lists/*
