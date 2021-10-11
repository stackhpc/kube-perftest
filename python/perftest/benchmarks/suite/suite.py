from datetime import datetime
import json
import math
import re

import kopf
import kubernetes

from ... import custom_resource, util
from .. import BENCHMARKS_API_GROUP, ALL


#: Custom resource for a suite of similar benchmarks
suite = custom_resource.CustomResource(
    group = BENCHMARKS_API_GROUP,
    versions = (custom_resource.Version('v1alpha1'), ),
    kind = 'Suite'
)


@suite.on_create()
def on_create(spec, patch, **kwargs):
    """
    Executes when a new benchmark suite is created.
    """
    dimensions = list(spec["matrix"].keys())
    patch.update({
        "status": {
            # List of dimensions in the order we will vary them from fastest to slowest
            "dimensions": dimensions,
            # The size of each dimension
            "shape": [len(spec["matrix"][dim]) for dim in dimensions],
            # The current index within each dimension
            "pointer": [0] * len(spec["matrix"]),
            # List of names of completed benchmarks
            "completed": [],
            # The total number of benchmarks to execute
            "count": math.prod(len(d) for d in spec["matrix"].values()),
            # The number of benchmarks that have succeeded
            "succeeded": 0,
            # The number of benchmarks that have failed
            "failed": 0,
        }
    })


def interpolate(obj, matrix):
    """
    Interpolate the values from the given matrix into the given object.
    """
    if isinstance(obj, dict):
        return { key: interpolate(value, matrix) for key, value in obj.items() }
    if isinstance(obj, list):
        return [interpolate(item, matrix) for item in obj]
    if isinstance(obj, str):
        match = re.match(r"^__MATRIX__\[(?P<key>[^\]]+)\]$", obj)
        if match is not None:
            return matrix[match.group("key")]
    return obj


@suite.on_update(field = "status.pointer")
def on_pointer_changed(namespace, name, spec, status, **kwargs):
    """
    Executes when the pointer of a suite changes.
    """
    # When the pointer of a suite changes, launch a new benchmark using the
    # values at the pointer indices
    matrix = {
        key: spec["matrix"][key][index]
        for key, index in zip(status["dimensions"], status["pointer"])
    }
    # Build the benchmark object
    api_version = spec["template"].get("apiVersion", suite.current_version.name)
    benchmark = {
        "apiVersion": f"{BENCHMARKS_API_GROUP}/{api_version}",
        "kind": spec["template"]["kind"],
        "metadata": {
            "namespace": namespace,
            "generateName": f"{name}-",
            "labels": {
                "app.kubernetes.io/part-of": name,
            },
            "annotations": {
                "perftest.stackhpc.com/matrix-values": json.dumps(matrix),
            },
        },
        "spec": interpolate(spec["template"]["spec"], matrix),
    }
    kopf.adopt(benchmark)
    # Find the plural name that we need to use to create the benchmark
    plural_name = next(b.plural_name for b in ALL() if b.kind == spec["template"]["kind"])
    # Then create the benchmark
    api = kubernetes.client.CustomObjectsApi()
    with util.suppress_already_exists():
        api.create_namespaced_custom_object(
            BENCHMARKS_API_GROUP,
            api_version,
            namespace,
            plural_name,
            benchmark
        )


@suite.on_owned_resource_event(BENCHMARKS_API_GROUP, kopf.EVERYTHING)
def on_benchmark_event(owner, namespace, name, spec, status, **kwargs):
    """
    Executes when an event occurs for any benchmark objects that are owned by a suite.
    """
    # We are only interested in finished benchmarks
    if status["phase"] not in {"Succeeded", "Failed"}:
        return
    # If the benchmark has already been seen as completed, ignore it
    completed = owner["status"].get("completed", [])
    if name in completed:
        return
    # When a job becomes either succeeded or failed, record that we have seen it
    patch = { "completed": completed + [name] }
    # Increment the relevant count depending on the benchmark status
    if status["phase"] == "Succeeded":
        patch.update(succeeded = owner["status"]["succeeded"] + 1)
    else:
        patch.update(failed = owner["status"]["failed"] + 1)
    # Increment the pointer
    shape = owner["status"]["shape"]
    pointer = owner["status"]["pointer"]
    for idx, (size, loc) in enumerate(zip(shape, pointer)):
        if loc + 1 < size:
            pointer[idx] = loc + 1
            break
        else:
            pointer[idx] = 0
    # If the pointer is reset back to zero we are done
    if any(p > 0 for p in pointer):
        patch.update(pointer = pointer)
    else:
        patch.update({ "finishedAt": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ') })
    # Apply the patch
    with util.suppress_not_found():
        suite.apply_patch(namespace, owner["metadata"]["name"], { "status": patch })


# @fio.on_update(field = "status.phase")
# def on_phase_changed(namespace, name, spec, status, **kwargs):
#     """
#     Executes when the phase of a fio benchmark changes.
#     """
#     # We only need to handle the succeeded phase
#     if status['phase'] != Phase.SUCCEEDED:
#         return
#     # If the results have not been logged for each client, schedule a retry
#     clients = spec['clients']
#     results = status.get('results', {})
#     if len(results) < clients:
#         raise kopf.TemporaryError('Results are not yet available')
#     # Once we have a result for each client, delete the job and config map
#     selector = fio.subresource_label_selector(name = name)
#     corev1 = kubernetes.client.CoreV1Api()
#     corev1.delete_collection_namespaced_config_map(namespace, label_selector = selector)
#     corev1.delete_collection_namespaced_persistent_volume_claim(namespace, label_selector = selector)
#     batchv1 = kubernetes.client.BatchV1Api()
#     batchv1.delete_collection_namespaced_job(
#         namespace,
#         label_selector = selector,
#         propagation_policy = "Foreground"
#     )


# @fio.on_update(field = "status.job")
# def on_component_phase_changed(status, spec, patch, **kwargs):
#     """
#     Executes when the job status of a fio benchmark changes.
#     """
#     phase = next_phase = status['phase']
#     job_status = status.get('job')
#     if job_status:
#         completed = bool(status.get('finishedAt'))
#         clients = spec['clients']
#         active = job_status['active']
#         succeeded = job_status['succeeded']
#         if completed:
#             next_phase = Phase.SUCCEEDED if succeeded >= clients else Phase.FAILED
#         else:
#             next_phase = Phase.RUNNING if active > 0 else Phase.PENDING
#     elif phase in {Phase.PENDING, Phase.RUNNING}:
#         next_phase = Phase.UNKNOWN
#     if phase != next_phase:
#         patch.setdefault('status', {}).update(phase = next_phase)


# @fio.on_update(field = "status.results")
# def on_output_changed(status, spec, patch, **kwargs):
#     """
#     Executes when the results change for any client and re-calculates the summary result.
#     """
#     clients = spec["clients"]
#     results = status.get("results", {})
#     if len(results) < clients:
#         return
#     section = "read" if spec["mode"].endswith("read") else "write"
#     bw_mean = sum(r["output"]["jobs"][0][section]["bw_mean"] for r in results.values()) / clients
#     patch.setdefault('status', {}).update(summary = f"{bw_mean:.2f} KiB/sec")


# @fio.on_subresource_event('batch', 'job')
# @util.suppress_not_found()
# def on_job_event(type, namespace, labels, status, **kwargs):
#     """
#     Executes when an event occurs for a job that is a subresource of an fio benchmark.
#     """
#     if type != "DELETED":
#         active = status.get("active", 0)
#         succeeded = status.get("succeeded", 0)
#         failed = status.get("failed", 0)
#         status_parts = []
#         if active > 0:
#             status_parts.append(f"{active} active")
#         if succeeded > 0:
#             status_parts.append(f"{succeeded} succeeded")
#         if failed > 0:
#             status_parts.append(f"{failed} failed")
#         patch = {
#             "status": {
#                 "job": {
#                     "status": " / ".join(status_parts) or None,
#                     "active": active,
#                     "succeeded": succeeded,
#                     "failed": failed,
#                 },
#             },
#         }
#     else:
#         patch = { "status": { "job": None }, }
#     # If the job is completed, also update the finished time
#     completion_time = status.get("completionTime")
#     if completion_time:
#         patch.setdefault("status", {}).update({ "finishedAt": completion_time })
#     fio.apply_patch(namespace, labels["app.kubernetes.io/instance"], patch)


# @fio.on_subresource_event('pod')
# @util.suppress_not_found()
# def on_pod_event(namespace, name, labels, spec, status, **kwargs):
#     """
#     Executes when an event occurs for a pod that is a subresource of an fio benchmark.
#     """
#     # When a client pod succeeds, we need to record the result from it
#     # The pod log should be a JSON-formatted object
#     # We also record the node that the pod was scheduled on
#     if status["phase"] == "Succeeded":
#         corev1 = kubernetes.client.CoreV1Api()
#         # The content preloading converts JSON-formatted logs to a Python object and back
#         # to a string, which turns all the quotes into single quotes and means it is not
#         # valid JSON anymore
#         # Accessing the raw response directly avoids this
#         logs = corev1.read_namespaced_pod_log(name, namespace, _preload_content = False).data
#         output = json.loads(logs)
#         patch = {
#             "status": {
#                 "results": {
#                     name: {
#                         "nodeName": spec["nodeName"],
#                         "nodeIP": status["hostIP"],
#                         "output": output,
#                     },
#                 },
#             },
#         }
#         fio.apply_patch(namespace, labels["app.kubernetes.io/instance"], patch)
