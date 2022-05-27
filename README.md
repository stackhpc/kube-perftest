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

kubectl get fioset
NAME         COUNT   SUCCEEDED   FAILED   CREATED   FINISHED
fio-cinder   24      0           0        7s
```

For more example perf tests please see:
https://github.com/stackhpc/kube-perftest/tree/main/examples
