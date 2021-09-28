#!/usr/bin/env bash

set -e

#####
## Run the iperf performance test
#####

echo "[INFO] Installing kube-perftest helm repository"
helm repo add perftest https://stackhpc.github.io/kube-perftest > /dev/null
helm repo update > /dev/null

# Generate a name for the job
JOBNAME="perftest-iperf-$(cat /dev/urandom | tr -dc 'a-z0-9' | head -c 5)"

# Run the job by installing the helm chart and get the chart name
echo "[INFO] Launching job - $JOBNAME"
helm install $JOBNAME perftest/iperf \
  --devel \
  --wait \
  --wait-for-jobs \
  > /dev/null

serverlabels="app.kubernetes.io/instance=$JOBNAME,app.kubernetes.io/component=server"
clientlabels="app.kubernetes.io/instance=$JOBNAME,app.kubernetes.io/component=client"

# Print information about where the pods were scheduled
servernode="$(kubectl get po -l $serverlabels -o go-template='{{ (index .items 0).spec.nodeName }}')"
echo "[INFO] Server scheduled on node - $servernode"
clientnode="$(kubectl get po -l $clientlabels -o go-template='{{ (index .items 0).spec.nodeName }}')"
echo "[INFO] Client scheduled on node - $clientnode"

# Print the logs from the server
kubectl logs -l $serverlabels

# Delete the resources for the job
echo "[INFO] Cleaning up job resources"
helm delete $JOBNAME > /dev/null

echo "[DONE]"
