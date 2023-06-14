#####
# Dockerfile for service readiness discovery
#####

FROM debian:bookworm-slim


RUN apt-get update && \
    apt-get install -y iproute2 netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*
