import re

import kopf
import kubernetes

from ... import custom_resource, util


class Phase:
    """
    Container for possible statuses for the iPerf benchmark.
    """
    PENDING   = "Pending"
    RUNNING   = "Running"
    SUCCEEDED = "Succeeded"
    FAILED    = "Failed"
    UNKNOWN   = "Unknown"


iperf = custom_resource.CustomResource.initialise_from_template("crd.yaml")


@iperf.on_create()
def on_create(namespace, name, spec, patch, **kwargs):
    """
    Executes when a new iperf benchmark is created.
    """
    # Create the server service
    service = iperf.from_template("server-service.yaml", name = name, spec = spec)
    kopf.adopt(service)
    corev1 = kubernetes.client.CoreV1Api()
    with util.suppress_already_exists():
        service = corev1.create_namespaced_service(namespace, service)
    # Create the server deployment
    deployment = iperf.from_template("server-deployment.yaml", name = name, spec = spec)
    kopf.adopt(deployment)
    appsv1 = kubernetes.client.AppsV1Api()
    with util.suppress_already_exists():
        deployment = appsv1.create_namespaced_deployment(namespace, deployment)
    # Create the job for the client
    job = iperf.from_template("client-job.yaml", name = name, spec = spec)
    kopf.adopt(job)
    batchv1 = kubernetes.client.BatchV1Api()
    with util.suppress_already_exists():
        job = batchv1.create_namespaced_job(namespace, job)
    # Update the status to reflect the fact that the resources were created
    patch.setdefault('status', {}).update(phase = Phase.PENDING)


@iperf.on_update(field = "status.phase")
def on_phase_changed(namespace, name, status, **kwargs):
    """
    Executes when the phase of an iperf benchmark changes.
    """
    # We only need to handle the succeeded phase
    if status['phase'] != Phase.SUCCEEDED:
        return
    # If the output is not set yet, schedule a retry
    if not status.get('output'):
        raise kopf.TemporaryError('Output is not yet available')
    # If the output is available, delete the resources for the benchmark
    selector = iperf.subresource_label_selector(name = name)
    corev1 = kubernetes.client.CoreV1Api()
    # Annoyingly, services do not have a delete collection method
    services = corev1.list_namespaced_service(namespace, label_selector = selector)
    for services in services.items:
        corev1.delete_namespaced_service(services.metadata.name, namespace)
    appsv1 = kubernetes.client.AppsV1Api()
    appsv1.delete_collection_namespaced_deployment(namespace, label_selector = selector)
    batchv1 = kubernetes.client.BatchV1Api()
    batchv1.delete_collection_namespaced_job(
        namespace,
        label_selector = selector,
        propagation_policy = "Foreground"
    )


@iperf.on_update(field = "status.server.phase")
@iperf.on_update(field = "status.client.phase")
def on_component_phase_changed(status, patch, **kwargs):
    """
    Executes when the phase of one of the components of an iperf benchmark changes.
    """
    # Work out the next overall phase based on the component phases
    phase = next_phase = status['phase']
    client_phase = status.get('client', {}).get('phase')
    server_phase = status.get('server', {}).get('phase')
    if client_phase == util.JobPhase.RUNNING and server_phase == util.DeploymentPhase.AVAILABLE:
        next_phase = Phase.RUNNING
    elif client_phase == util.JobPhase.SUCCEEDED:
        next_phase = Phase.SUCCEEDED
    elif client_phase == util.JobPhase.FAILED:
        next_phase = Phase.FAILED
    # If the phase has changed, add it to the patch
    if phase != next_phase:
        patch.setdefault('status', {}).update(phase = next_phase)


@iperf.on_update(field = "status.output")
def on_output_changed(status, patch, **kwargs):
    """
    Executes when the output changes and re-calculates the summary result.
    """
    # When the output changes, recalculate the result
    # To do this, extract the Gbit/sec from the last line that contains it
    result = None
    for output_line in reversed(status['output'].splitlines()):
        match = re.search(r"\d+\.\d+ Gbits/sec", output_line)
        if match is not None:
            result = match.group(0)
            break
    patch.setdefault('status', {}).update(result = result)


@iperf.on_subresource_event('apps', 'deployment')
@util.suppress_not_found()
def on_deployment_event(type, body, namespace, labels, **kwargs):
    """
    Executes when an event occurs for a deployment that is a subresource of an iperf benchmark.
    """
    if type == "DELETED":
        phase = "Terminated"
    else:
        phase = util.deployment_phase(body)
    patch = dict(status = dict(server = dict(phase = phase)))
    iperf.apply_patch(namespace, labels["app.kubernetes.io/instance"], patch)


@iperf.on_subresource_event('batch', 'job')
@util.suppress_not_found()
def on_job_event(type, body, namespace, labels, **kwargs):
    """
    Executes when an event occurs for a job that is a subresource of an iperf benchmark.
    """
    if type == "DELETED":
        phase = "Terminated"
    else:
        phase = util.job_phase(body)
    patch = dict(status = dict(client = dict(phase = phase)))
    # If the job is completed, also update the finished time
    completion_time = body['status'].get('completionTime')
    if completion_time:
        patch['status'].update(finishedAt = completion_time)
    iperf.apply_patch(namespace, labels["app.kubernetes.io/instance"], patch)


@iperf.on_subresource_event('pod')
@util.suppress_not_found()
def on_pod_event(namespace, name, labels, spec, status, **kwargs):
    """
    Executes when an event occurs for a pod that is a subresource of an iperf benchmark.
    """
    patch = {}
    component = labels["app.kubernetes.io/component"]
    phase = status["phase"]
    # When a running pod becomes ready, store information about the node it was scheduled on
    ready = any(c["type"] == "Ready" and c["status"] == "True" for c in status["conditions"])
    if phase == "Running" and ready:
        patch.setdefault('status', {}).setdefault(component, {}).update({
            'nodeName': spec['nodeName'],
            'nodeIP':   status['hostIP'],
        })
    # When a client pod succeeds, store the pod output as the benchmark result
    if component == "client" and phase == "Succeeded":
        corev1 = kubernetes.client.CoreV1Api()
        output = corev1.read_namespaced_pod_log(name, namespace)
        patch.setdefault('status', {}).update(output = output)
    if patch:
        iperf.apply_patch(namespace, labels["app.kubernetes.io/instance"], patch)
