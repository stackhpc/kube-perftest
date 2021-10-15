import copy
from datetime import datetime
import json
import math
import re

import kopf
import kubernetes

from ... import custom_resource, util
from .fio import fio as fio_cr, Phase as FioPhase


fioset = custom_resource.CustomResource.initialise_from_template("crd/fioset.yaml")


@fioset.on_create()
def on_create(namespace, name, spec, patch, **kwargs):
    """
    Executes when a new fioset is created.
    """
    # Check that either a claim name or template is specified
    if not spec.get("volumeClaimName") and not spec.get("volumeClaimTemplate"):
        raise kopf.PermanentError("One of volumeClaimName or volumeClaimTemplate is required")
    # Create the PVC that will be used for the sub-jobs
    # If a PVC name is given, that takes precedence over a managed PVC
    if not spec.get("volumeClaimName"):
        # Create the PVC using the template
        pvc_name = f"{name}-fio-scratch"
        pvc = spec["volumeClaimTemplate"]
        # Add the required name
        pvc.setdefault("metadata", {})["name"] = pvc_name
        # Add the labels that make it a subresource
        subresource_labels = fioset.subresource_labels(name = name)
        pvc.setdefault("metadata", {}).setdefault("labels", {}).update(subresource_labels)
        # Set the access mode correctly - more than one client requires RWX
        pvc["spec"]["accessModes"] = [
            "ReadWriteMany" if any(c > 1 for c in spec["clients"]) else "ReadWriteOnce",
        ]
        kopf.adopt(pvc)
        corev1 = kubernetes.client.CoreV1Api()
        with util.suppress_already_exists():
            corev1.create_namespaced_persistent_volume_claim(namespace, pvc)
        # Update the volume claim name
        patch.setdefault("spec", {}).update({ "volumeClaimName": pvc_name })
    # The items are a cross-product of the clients, modes and blocksizes
    items = [
        dict(clients = clients, mode = mode, blocksize = blocksize)
        for mode in spec["modes"]
        for clients in spec["clients"]
        for blocksize in spec["blocksizes"]
    ]
    patch.update({
        "status": {
            # The total number of benchmarks to execute
            "count": len(items),
            # List of dimensions in the order we will vary them from fastest to slowest
            "items": items,
            # The number of benchmarks that have succeeded
            "succeeded": 0,
            # The number of benchmarks that have failed
            "failed": 0,
        }
    })


@fioset.on_update(field = "status.succeeded")
@fioset.on_update(field = "status.failed")
def on_fio_completed(namespace, name, spec, status, patch, **kwargs):
    """
    Executes when the succeeded or failed counts are updated.
    """
    # When the succeeded or failed counts are updated, launch the next fio instance
    items = status.get("items", [])
    succeeded = status.get("succeeded", 0)
    failed = status.get("failed", 0)
    next_idx = succeeded + failed
    # Create the next fio instance unless we are done
    if next_idx < len(items):
        # We want to use a padded index so that the ordering in the CLI is nice
        # To do that, we need to know how many chars to pad to
        nchars = int(math.log10(len(items))) + 1
        padded_idx = str(next_idx).zfill(nchars)
        # Build the fio object to use
        fio = {
            "apiVersion": f"{fio_cr.group}/{fio_cr.version}",
            "kind": fio_cr.kind,
            "metadata": {
                "namespace": namespace,
                "name": f"{name}-{padded_idx}",
                "labels": fioset.subresource_labels(name = name),
            },
            "spec": {
                key: value
                for key, value in dict(
                    # Drop the keys that are not required from the fioset spec
                    **{
                        k: v
                        for k, v in spec.items()
                        if k not in {"clients", "modes", "blocksizes", "volumeClaimTemplate"}
                    },
                    # And include the keys from the current item
                    **items[next_idx]
                ).items()
            },
        }
        kopf.adopt(fio)
        api = kubernetes.client.CustomObjectsApi()
        with util.suppress_already_exists():
            api.create_namespaced_custom_object(
                fio_cr.group,
                fio_cr.version,
                namespace,
                fio_cr.plural_name,
                fio
            )
    else:
        # If we are done, record the finish time
        patch.setdefault("status", {}).update({
            "finishedAt": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        })
        # And delete the managed PVC if there is one
        corev1 = kubernetes.client.CoreV1Api()
        corev1.delete_collection_namespaced_persistent_volume_claim(
            namespace,
            label_selector = fioset.subresource_label_selector(name = name)
        )


@fioset.on_owned_resource_event(fio_cr.group, fio_cr.singular_name)
@util.suppress_not_found()
def on_fio_event(owner, namespace, name, spec, status, **kwargs):
    """
    Executes when an event occurs for a fio instance that is owned by a fioset.
    """
    # We are only interested in finished benchmarks
    if status["phase"] not in {FioPhase.SUCCEEDED, FioPhase.FAILED}:
        return
    # If the benchmark has already been seen as completed, ignore it
    completed = owner["status"].get("completed", [])
    if name in completed:
        return
    # When a job becomes either succeeded or failed, record that we have seen it
    patch = { "completed": completed + [name] }
    # Increment the relevant count depending on the benchmark status
    if status["phase"] == FioPhase.SUCCEEDED:
        patch.update(succeeded = owner["status"]["succeeded"] + 1)
    else:
        patch.update(failed = owner["status"]["failed"] + 1)
    # Apply the patch
    with util.suppress_not_found():
        fioset.apply_patch(namespace, owner["metadata"]["name"], { "status": patch })
