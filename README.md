# kube-perftest

To install the helm chart:

```
helm repo add perftest https://stackhpc.github.io/kube-perftest
helm upgrade perftest-operator perftest/perftest-operator -i --devel
```

```
cat >fio-cinder.yaml << EOF
apiVersion: perftest.stackhpc.com/v1alpha1
kind: FioSet
metadata:
  name: fio-cinder
spec:
  imagePullPolicy: Always
  # Cinder volumes can only have one client
  clients: [1]
  modes: [read, randread, write, randwrite]
  # [1k, 4k, 64k, 256k, 1m, 2m]
  blocksizes: [1024, 4096, 65536, 262144, 1048576, 2097152]
  filesize: 4g
  volumeClaimTemplate:
    spec:
      storageClassName: csi-cinder
      resources:
        requests:
          storage: 50Gi
EOF

kubectl create -f fio-cinder.yaml

$ kubectl get fioset
NAME         COUNT   SUCCEEDED   FAILED   CREATED   FINISHED
fio-cinder   24      2           0        12m

$ kubectl get fio
NAME            MODE   CLIENTS   BLOCK SIZE   FILE SIZE   RUNTIME   STATUS      CREATED   FINISHED   BANDWIDTH     IOPS       LATENCY
fio-cinder-00   read   1         1024         4g          30        Succeeded   12m       9m15s      5.740 MiB/s   5878.490   5.421 ms
fio-cinder-01   read   1         4096         4g          30        Succeeded   8m49s     6m41s      9.027 MiB/s   2311.153   13.805 ms
fio-cinder-02   read   1         65536        4g          30        Running     6m39s
```

For more example perf tests please see:
https://github.com/stackhpc/kube-perftest/tree/main/examples
