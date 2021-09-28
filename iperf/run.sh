#!/usr/bin/env bash

set -ex

#####
## Run the iperf performance test
#####

helm repo add perftest https://stackhpc.github.io/kube-perftest
helm repo update

# Generate a name for the job
JOBNAME="perftest-iperf-$(cat /dev/urandom | tr -dc 'a-z0-9' | head -c 5)"

# Run the job by installing the helm chart and get the chart name
helm install $JOBNAME perftest/iperf --devel --set fullnameOverride=$JOBNAME --wait --wait-for-jobs

# Print the logs from the server
kubectl logs deployment/$JOBNAME-server

# Delete the resources for the job
helm delete $JOBNAME
