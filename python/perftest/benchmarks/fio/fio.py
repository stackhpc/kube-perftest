import json
import math

import kopf
import kubernetes

from ... import custom_resource, util


class Phase:
    """
    Container for possible statuses for the fio benchmark.
    """
    PENDING      = "Pending"
    INITIALISING = "Initialising"
    RUNNING      = "Running"
    SUCCEEDED    = "Succeeded"
    FAILED       = "Failed"
    UNKNOWN      = "Unknown"


#: Benchmark implementation that runs fio
fio = custom_resource.CustomResource.initialise_from_template("crds/fio.yaml")


@fio.on_create()
def on_create(namespace, name, spec, patch, **kwargs):
    """
    Executes when a new fio benchmark is created.
    """
    # Check that either a claim name or template is specified
    if not spec.get("volumeClaimName") and not spec.get("volumeClaimTemplate"):
        raise kopf.PermanentError("One of volumeClaimName or volumeClaimTemplate is required")
    # Create the configmap with the job configuration
    config_map = fio.from_template("configmap.yaml", name = name, spec = spec)
    kopf.adopt(config_map)
    corev1 = kubernetes.client.CoreV1Api()
    with util.suppress_already_exists():
        corev1.create_namespaced_config_map(namespace, config_map)
    # If a PVC name is given, that takes precedence over a managed PVC
    pvc_name = spec.get("volumeClaimName")
    if not pvc_name:
        # Create the PVC using the template
        pvc_name = f"{name}-fio-scratch"
        pvc = spec["volumeClaimTemplate"]
        # Add the required name
        pvc.setdefault("metadata", {})["name"] = pvc_name
        # Add the labels that make it a subresource
        subresource_labels = fio.subresource_labels(name = name)
        pvc.setdefault("metadata", {}).setdefault("labels", {}).update(subresource_labels)
        # Set the access mode correctly - more than one client requires RWX
        pvc["spec"]["accessModes"] = ["ReadWriteMany" if spec["clients"] > 1 else "ReadWriteOnce"]
        kopf.adopt(pvc)
        with util.suppress_already_exists():
            corev1.create_namespaced_persistent_volume_claim(namespace, pvc)
    # Create the job
    job = fio.from_template("job.yaml", name = name, pvc_name = pvc_name, spec = spec)
    kopf.adopt(job)
    batchv1 = kubernetes.client.BatchV1Api()
    with util.suppress_already_exists():
        job = batchv1.create_namespaced_job(namespace, job)
    # Update the status to reflect the fact that the resources were created
    patch.setdefault("status", {}).update(phase = Phase.PENDING)


@fio.on_update(field = "status.phase")
def on_phase_changed(namespace, name, spec, status, **kwargs):
    """
    Executes when the phase of a fio benchmark changes.
    """
    # We only need to handle the succeeded phase
    if status["phase"] != Phase.SUCCEEDED:
        return
    # If the results have not been logged for each client, schedule a retry
    clients = spec["clients"]
    results = status.get("results", {})
    if len(results) < clients:
        raise kopf.TemporaryError("Results are not yet available")
    # Once we have a result for each client, delete the subresources
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


@fio.on_update(field = "status.pvc")
@fio.on_update(field = "status.job")
@fio.on_update(field = "status.pods")
def on_component_phase_changed(spec, status, patch, **kwargs):
    """
    Executes when the status of one of the components of a fio benchmark changes.
    """
    phase = next_phase = status["phase"]
    # Once the phase has transitioned to succeeded or failed, we are done
    if phase in { Phase.SUCCEEDED, Phase.FAILED }:
        return
    managed_pvc = not spec.get("volumeClaimName")
    pvc_phase = status.get("pvc", {}).get("phase", "Pending")
    job_phase = status.get("job", {}).get("phase", "Pending")
    pod_phases = { p["phase"] for p in status.get("pods", {}).values() }
    if managed_pvc and pvc_phase == "Pending":
        # If we are managing a PVC and it is pending, then the whole benchmark is pending
        next_phase = Phase.PENDING
    elif job_phase == util.JobPhase.PENDING:
        # If the job is pending, then the benchmark is pending
        next_phase = Phase.PENDING
    elif job_phase == util.JobPhase.RUNNING:
        # The job becomes running once there is at least one pod that is "active"
        # Those pods can still be scheduling or initialising
        if util.PodPhase.SCHEDULING in pod_phases:
            next_phase = Phase.PENDING
        elif util.PodPhase.INITIALISING in pod_phases:
            next_phase = Phase.INITIALISING
        else:
            next_phase = Phase.RUNNING
    elif job_phase == util.JobPhase.SUCCEEDED:
        next_phase = Phase.SUCCEEDED
    elif job_phase == util.JobPhase.FAILED:
        next_phase = Phase.FAILED
    else:
        next_phase = Phase.UNKNOWN
    if phase != next_phase:
        patch.setdefault("status", {}).update(phase = next_phase)


@fio.on_update(field = "status.results")
def on_results_changed(status, spec, patch, **kwargs):
    """
    Executes when the results change for any client and re-calculates the summary result.
    """
    clients = spec["clients"]
    results = status.get("results", {})
    if len(results) < clients:
        return
    section = "read" if spec["mode"].endswith("read") else "write"
    patch.setdefault("status", {})["summary"] = {
        # To get an aggregate bandwidth across all clients, we sum the bandwidth for each client
        "bandwidth": sum(r["jobs"][0][section]["bw"] for r in results.values()),
        # Similar for IOPS
        "iops": sum(r["jobs"][0][section]["iops"] for r in results.values()),
        # For latency, use the mean of the mean latencies for each client
        "latency": (
            sum(r["jobs"][0][section]["clat_ns"]["mean"] for r in results.values()) /
            clients
        ),
    }


@fio.on_subresource_event("persistentvolumeclaim")
@util.suppress_not_found()
def on_pvc_event(type, namespace, labels, status, **kwargs):
    """
    Executes when an event occurs for a pvc that is a subresource of a fio benchmark.
    """
    # Just store the phase of the PVC
    if type == "DELETED":
        phase = "Deleted"
    else:
        phase = status["phase"]
    fio.apply_patch(
        namespace,
        labels["app.kubernetes.io/instance"],
        { "status": { "pvc": { "phase": phase } } }
    )


@fio.on_subresource_event("batch", "job")
@util.suppress_not_found()
def on_job_event(type, namespace, labels, body, status, **kwargs):
    """
    Executes when an event occurs for a job that is a subresource of a fio benchmark.
    """
    if type == "DELETED":
        phase = "Terminated"
    else:
        phase = util.job_phase(body)
    patch = { "status": { "job": { "phase": phase } } }
    # If the job is completed, also update the finished time
    completion_time = status.get("completionTime")
    if completion_time:
        patch["status"].update({ "finishedAt": completion_time })
    fio.apply_patch(namespace, labels["app.kubernetes.io/instance"], patch)


@fio.on_subresource_event("pod")
@util.suppress_not_found()
def on_pod_event(type, namespace, name, labels, body, spec, status, **kwargs):
    """
    Executes when an event occurs for a pod that is a subresource of a fio benchmark.
    """
    # Always update the phase for the pod
    if type == "DELETED":
        phase = "Terminated"
    else:
        phase = util.pod_phase(body)
    print(f"POD PHASE: {phase}")
    patch = { "status": { "pods": { name: { "phase": phase } } } }
    # Update with the node that the pod was scheduled on, if the info is available
    if spec.get("nodeName") and status.get("hostIP"):
        patch["status"]["pods"][name].update({
            "nodeName": spec["nodeName"],
            "nodeIP": status["hostIP"],
        })
    # When a pod succeeds, we need to record the result from it
    # The pod log should be a JSON-formatted object
    if phase == util.PodPhase.SUCCEEDED:
        corev1 = kubernetes.client.CoreV1Api()
        # The content preloading converts JSON-formatted logs to a Python object and back
        # to a string, which turns all the quotes into single quotes and means it is not
        # valid JSON anymore
        # Accessing the raw response directly avoids this
        logs = corev1.read_namespaced_pod_log(name, namespace, _preload_content = False).data
        patch["status"]["results"] = { name: json.loads(logs) }
    fio.apply_patch(namespace, labels["app.kubernetes.io/instance"], patch)
