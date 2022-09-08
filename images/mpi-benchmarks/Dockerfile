#####
# Dockerfile for the Intel MPI benchmarks
# https://www.intel.com/content/www/us/en/develop/documentation/imb-user-guide/top.html
#####

FROM rockylinux:8.6

# We need SSHD to do MPI initialisation over SSH
RUN yum install -y openssh-clients openssh-server && \
    yum clean all -y && \
    rm -rf /var/cache

# Install the OpenMPI tests module
ARG MPITESTS_VERSION=5.8
RUN yum install -y "mpitests-openmpi-${MPITESTS_VERSION}" && \
    yum clean all -y && \
    rm -rf /var/cache

# Make sure the MPI binaries are on the PATH
ENV PATH=/usr/lib64/openmpi/bin:$PATH

# Install helper scripts
COPY ./scripts/* /usr/local/bin
