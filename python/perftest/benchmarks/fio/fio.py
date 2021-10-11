import json
import re

import kopf
import kubernetes

from ... import custom_resource, util
from .. import BENCHMARKS_API_GROUP


class Phase:
    """
    Container for possible statuses for the fio benchmark.
    """
    PENDING   = "Pending"
    RUNNING   = "Running"
    SUCCEEDED = "Succeeded"
    FAILED    = "Failed"
    UNKNOWN   = "Unknown"


#: Benchmark implementation that runs fio
fio = custom_resource.CustomResource(
    group = BENCHMARKS_API_GROUP,
    versions = (custom_resource.Version('v1alpha1'), ),
    kind = 'Fio'
)


@fio.on_create()
def on_create(namespace, name, spec, patch, **kwargs):
    """
    Executes when a new fio benchmark is created.
    """
    # Create the configmap with the job configuration
    config_map = fio.from_template("configmap.yaml", name = name, spec = spec)
    kopf.adopt(config_map)
    corev1 = kubernetes.client.CoreV1Api()
    with util.suppress_already_exists():
        corev1.create_namespaced_config_map(namespace, config_map)
    # Create the persistent volume claim for scratch
    pvc = fio.from_template("pvc.yaml", name = name, spec = spec)
    kopf.adopt(pvc)
    with util.suppress_already_exists():
        corev1.create_namespaced_persistent_volume_claim(namespace, pvc)
    # Create the job
    job = fio.from_template("job.yaml", name = name, spec = spec)
    kopf.adopt(job)
    batchv1 = kubernetes.client.BatchV1Api()
    with util.suppress_already_exists():
        job = batchv1.create_namespaced_job(namespace, job)
    # Update the status to reflect the fact that the resources were created
    patch.setdefault('status', {}).update(phase = Phase.PENDING)


@fio.on_update(field = "status.phase")
def on_phase_changed(namespace, name, spec, status, **kwargs):
    """
    Executes when the phase of a fio benchmark changes.
    """
    # We only need to handle the succeeded phase
    if status['phase'] != Phase.SUCCEEDED:
        return
    # If the results have not been logged for each client, schedule a retry
    clients = spec['clients']
    results = status.get('results', {})
    if len(results) < clients:
        raise kopf.TemporaryError('Results are not yet available')
    # Once we have a result for each client, delete the job and config map
    selector = fio.subresource_label_selector(name = name)
    corev1 = kubernetes.client.CoreV1Api()
    corev1.delete_collection_namespaced_config_map(namespace, label_selector = selector)
    corev1.delete_collection_namespaced_persistent_volume_claim(namespace, label_selector = selector)
    batchv1 = kubernetes.client.BatchV1Api()
    batchv1.delete_collection_namespaced_job(
        namespace,
        label_selector = selector,
        propagation_policy = "Foreground"
    )


@fio.on_update(field = "status.job")
def on_component_phase_changed(status, spec, patch, **kwargs):
    """
    Executes when the job status of a fio benchmark changes.
    """
    phase = next_phase = status['phase']
    job_status = status.get('job')
    if job_status:
        completed = bool(status.get('finishedAt'))
        clients = spec['clients']
        active = job_status['active']
        succeeded = job_status['succeeded']
        if completed:
            next_phase = Phase.SUCCEEDED if succeeded >= clients else Phase.FAILED
        else:
            next_phase = Phase.RUNNING if active > 0 else Phase.PENDING
    elif phase in {Phase.PENDING, Phase.RUNNING}:
        next_phase = Phase.UNKNOWN
    if phase != next_phase:
        patch.setdefault('status', {}).update(phase = next_phase)


@fio.on_update(field = "status.results")
def on_output_changed(status, spec, patch, **kwargs):
    """
    Executes when the results change for any client and re-calculates the summary result.
    """
    clients = spec["clients"]
    results = status.get("results", {})
    if len(results) < clients:
        return
    section = "read" if spec["mode"].endswith("read") else "write"
    bw_mean = sum(r["output"]["jobs"][0][section]["bw_mean"] for r in results.values()) / clients
    patch.setdefault('status', {}).update(summary = f"{bw_mean:.2f} KiB/sec")


@fio.on_subresource_event('batch', 'job')
@util.suppress_not_found()
def on_job_event(type, namespace, labels, status, **kwargs):
    """
    Executes when an event occurs for a job that is a subresource of an fio benchmark.
    """
    if type != "DELETED":
        active = status.get("active", 0)
        succeeded = status.get("succeeded", 0)
        failed = status.get("failed", 0)
        status_parts = []
        if active > 0:
            status_parts.append(f"{active} active")
        if succeeded > 0:
            status_parts.append(f"{succeeded} succeeded")
        if failed > 0:
            status_parts.append(f"{failed} failed")
        patch = {
            "status": {
                "job": {
                    "status": " / ".join(status_parts) or None,
                    "active": active,
                    "succeeded": succeeded,
                    "failed": failed,
                },
            },
        }
    else:
        patch = { "status": { "job": None }, }
    # If the job is completed, also update the finished time
    completion_time = status.get("completionTime")
    if completion_time:
        patch.setdefault("status", {}).update({ "finishedAt": completion_time })
    fio.apply_patch(namespace, labels["app.kubernetes.io/instance"], patch)


@fio.on_subresource_event('pod')
@util.suppress_not_found()
def on_pod_event(namespace, name, labels, spec, status, **kwargs):
    """
    Executes when an event occurs for a pod that is a subresource of an fio benchmark.
    """
    # When a client pod succeeds, we need to record the result from it
    # The pod log should be a JSON-formatted object
    # We also record the node that the pod was scheduled on
    if status["phase"] == "Succeeded":
        corev1 = kubernetes.client.CoreV1Api()
        # The content preloading converts JSON-formatted logs to a Python object and back
        # to a string, which turns all the quotes into single quotes and means it is not
        # valid JSON anymore
        # Accessing the raw response directly avoids this
        logs = corev1.read_namespaced_pod_log(name, namespace, _preload_content = False).data
        output = json.loads(logs)
        patch = {
            "status": {
                "results": {
                    name: {
                        "nodeName": spec["nodeName"],
                        "nodeIP": status["hostIP"],
                        "output": output,
                    },
                },
            },
        }
        fio.apply_patch(namespace, labels["app.kubernetes.io/instance"], patch)
