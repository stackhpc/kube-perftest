#####
# Dockerfile for the RDMA bandwidth and latency benchmarks
#####

FROM rockylinux:8.6

ARG PERFTEST_VERSION=4.5
RUN yum install -y "perftest-${PERFTEST_VERSION}" && \
    yum clean all -y && \
    rm -rf /var/cache
