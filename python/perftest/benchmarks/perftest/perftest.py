import kopf
import kubernetes

from ... import custom_resource, util


class Phase:
    """
    Container for possible phases for a perftest benchmark.
    """
    PENDING   = "Pending"
    RUNNING   = "Running"
    SUCCEEDED = "Succeeded"
    FAILED    = "Failed"
    UNKNOWN   = "Unknown"


rdma_bandwidth = custom_resource.CustomResource.initialise_from_template("crd.yaml")


@rdma_bandwidth.on_create()
def on_create(namespace, name, spec, **kwargs):
    """
    Executes when a new rdma_bandwidth benchmark is created.
    """
    # Create the server deployment
    deployment = rdma_bandwidth.from_template("server-deployment.yaml", name = name, spec = spec)
    kopf.adopt(deployment)
    appsv1 = kubernetes.client.AppsV1Api()
    with util.suppress_already_exists():
        deployment = appsv1.create_namespaced_deployment(namespace, deployment)


@rdma_bandwidth.on_update(field = "status.server.phase")
def on_server_phase_changed(namespace, name, spec, status, **kwargs):
    """
    Executes when the server phase of an rdma_bandwidth benchmark changes.
    """
    # Wait for the deployment to reach the AVAILABLE phase
    server_phase = status.get("server", {}).get("phase")
    if not server_phase or server_phase != util.DeploymentPhase.AVAILABLE:
        return
    server_ip = status.get("server", {}).get("podIP")
    if not server_ip:
        raise kopf.TemporaryError("Unable to determine server IP")
    # Create the job for the client
    job = rdma_bandwidth.from_template("client-job.yaml", name = name, spec = spec, server_ip = server_ip)
    kopf.adopt(job)
    batchv1 = kubernetes.client.BatchV1Api()
    with util.suppress_already_exists():
        job = batchv1.create_namespaced_job(namespace, job)


@rdma_bandwidth.on_update(field = "status.phase")
def on_phase_changed(namespace, name, status, **kwargs):
    """
    Executes when the phase of an rdma_bandwidth benchmark changes.
    """
    # We only need to handle the succeeded phase
    if status["phase"] != Phase.SUCCEEDED:
        return
    # If the output is not set yet, schedule a retry
    if not status.get("output"):
        raise kopf.TemporaryError("Output is not yet available")
    # If the output is available, delete the resources for the benchmark
    selector = rdma_bandwidth.subresource_label_selector(name = name)
    appsv1 = kubernetes.client.AppsV1Api()
    appsv1.delete_collection_namespaced_deployment(namespace, label_selector = selector)
    batchv1 = kubernetes.client.BatchV1Api()
    batchv1.delete_collection_namespaced_job(
        namespace,
        label_selector = selector,
        propagation_policy = "Foreground"
    )


@rdma_bandwidth.on_update(field = "status.server.phase")
@rdma_bandwidth.on_update(field = "status.client.phase")
def on_component_phase_changed(status, patch, **kwargs):
    """
    Executes when the phase of one of the components of an rdma_bandwidth benchmark changes.
    """
    # Work out the next overall phase based on the component phases
    phase = next_phase = status["phase"]
    client_phase = status.get("client", {}).get("phase")
    server_phase = status.get("server", {}).get("phase")
    if client_phase == util.JobPhase.RUNNING and server_phase == util.DeploymentPhase.AVAILABLE:
        next_phase = Phase.RUNNING
    elif client_phase == util.JobPhase.SUCCEEDED:
        next_phase = Phase.SUCCEEDED
    elif client_phase == util.JobPhase.FAILED:
        next_phase = Phase.FAILED
    # If the phase has changed, add it to the patch
    if phase != next_phase:
        patch.setdefault("status", {}).update(phase = next_phase)


@rdma_bandwidth.on_update(field = "status.output")
def on_output_changed(status, patch, **kwargs):
    """
    Executes when the output changes and re-calculates the summary result.
    """
    # Find the start of the results table
    results_iter = iter(status["output"].splitlines())
    for output_line in results_iter:
        if output_line.strip().startswith("#bytes"):
            break
    # Get the average bandwidth from each line
    averages = []
    for output_line in results_iter:
        if output_line.startswith("-----"):
            break
        averages.append(float(output_line.split()[3]))
    patch.setdefault("status", {}).update(result = f"{max(averages)} MB/sec")


@rdma_bandwidth.on_subresource_event("apps", "deployment")
@util.suppress_not_found()
def on_deployment_event(type, body, namespace, labels, **kwargs):
    """
    Executes when an event occurs for a deployment that is a subresource of an rdma_bandwidth benchmark.
    """
    if type == "DELETED":
        phase = "Terminated"
    else:
        phase = util.deployment_phase(body)
    patch = dict(status = dict(server = dict(phase = phase)))
    rdma_bandwidth.apply_patch(namespace, labels["app.kubernetes.io/instance"], patch)


@rdma_bandwidth.on_subresource_event("batch", "job")
@util.suppress_not_found()
def on_job_event(type, body, namespace, labels, **kwargs):
    """
    Executes when an event occurs for a job that is a subresource of an rdma_bandwidth benchmark.
    """
    if type == "DELETED":
        phase = "Terminated"
    else:
        phase = util.job_phase(body)
    patch = dict(status = dict(client = dict(phase = phase)))
    # If the job is completed, also update the finished time
    completion_time = body["status"].get("completionTime")
    if completion_time:
        patch["status"].update(finishedAt = completion_time)
    rdma_bandwidth.apply_patch(namespace, labels["app.kubernetes.io/instance"], patch)


@rdma_bandwidth.on_subresource_event("pod")
@util.suppress_not_found()
def on_pod_event(namespace, name, labels, spec, status, **kwargs):
    """
    Executes when an event occurs for a pod that is a subresource of an rdma_bandwidth benchmark.
    """
    patch = {}
    component = labels["app.kubernetes.io/component"]
    phase = status["phase"]
    # When a running pod becomes ready, store information about the node it was scheduled on
    ready = any(
        condition["type"] == "Ready" and condition["status"] == "True"
        for condition in status.get("conditions", [])
    )
    if phase == "Running" and ready:
        patch.setdefault("status", {}).setdefault(component, {}).update({
            "podIP": status["podIP"],
            "nodeName": spec["nodeName"],
            "nodeIP": status["hostIP"],
        })
    # When a client pod succeeds, store the pod output as the benchmark result
    if component == "client" and phase == "Succeeded":
        corev1 = kubernetes.client.CoreV1Api()
        output = corev1.read_namespaced_pod_log(name, namespace)
        patch.setdefault("status", {}).update(output = output)
    if patch:
        rdma_bandwidth.apply_patch(namespace, labels["app.kubernetes.io/instance"], patch)
