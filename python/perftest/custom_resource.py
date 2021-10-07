from dataclasses import dataclass
import inspect

import jinja2
import kopf
import kubernetes
import yaml


@dataclass
class Version:
    """
    Class representing an API version for a custom resource.
    """
    #: The name of the version
    name: str
    #: Indicates if the version is deprecated
    deprecated: bool = False
    #: Indicates if the version should be served
    served: bool = True

    def __post_init__(self):
        # If a version is not being served, it should also be deprecated
        if not self.served and not self.deprecated:
            raise ValueError('CRD versions should be deprecated before stopping serving')


class CustomResource:
    """
    Class for defining a custom resource.
    """
    def __init__(
        self,
        *,
        group,
        versions,
        kind,
        singular_name = None,
        plural_name = None,
        short_names = None,
        template_module_name = None
    ):
        self.group = group
        self.versions = versions
        self.current_version = versions[-1]
        self.kind = kind
        self.singular_name = singular_name or self.kind.lower()
        self.plural_name = plural_name or f"{self.singular_name}s"
        self.short_names = short_names or []
        # If no template module was given, detect it using the call stack
        if not template_module_name:
            frame = inspect.stack()[1][0]
            module = inspect.getmodule(frame)
            # Assume that the module containing the calling code is a submodule
            # of the module containing the templates directory
            template_module_name = module.__name__.rsplit(".", maxsplit = 1)[0]
        self.template_module_name = template_module_name

    @property
    def full_name(self):
        """
        The full name of the custom resource.
        """
        return f"{self.plural_name}.{self.group}"

    @property
    def env(self):
        """
        A Jinja2 environment for this custom resource.

        The environment is lazy-loaded when first requested and cached for the duration
        of the object.

        Assumes that this custom resource is defined in a submodule of a module that also
        contains a templates directory.
        """
        if not hasattr(self, '__env'):
            self.__env = jinja2.Environment(
                loader = jinja2.PackageLoader(self.template_module_name),
                autoescape = False
            )
            # Register an additional filter for rendering subresource labels
            def subresource_labels(name = None, component = None):
                return yaml.safe_dump(self.subresource_labels(name = name, component = component))
            self.__env.globals['subresource_labels'] = subresource_labels
            # Also register a filter that produces match expressions for subresource labels for
            # use in pod [anti]affinity rules
            def match_expressions(name = None, component = None):
                labels = self.subresource_labels(name = name, component = component)
                return yaml.safe_dump([
                    dict(key = label, operator = "In", values = [value])
                    for label, value in labels.items()
                ])
            self.__env.globals['match_expressions'] = match_expressions
        return self.__env

    def from_template(self, template, **kwargs):
        """
        Renders the given template with the given kwargs, loads the result as YAML and returns it.
        """
        return yaml.safe_load(self.env.get_template(template).render(**kwargs))

    def make_crd(self):
        """
        Returns a CRD for this custom resource.
        """
        crd_versions = []
        for version in self.versions:
            crd_version = self.from_template(f"versions/{version.name}.yaml")
            crd_version.update(
                name = version.name,
                deprecated = version.deprecated,
                served = version.served,
                storage = version == self.current_version
            )
            crd_versions.append(crd_version)
        return {
            "apiVersion": "apiextensions.k8s.io/v1",
            "kind": "CustomResourceDefinition",
            "metadata": {
                "name": self.full_name,
            },
            "spec": {
                "group": self.group,
                "scope": "Namespaced",
                "names": {
                    "plural": self.plural_name,
                    "singular": self.singular_name,
                    "kind": self.kind,
                    "shortNames": self.short_names,
                },
                "versions": crd_versions,
            },
        }

    def register_crd(self):
        """
        Registers the CRD for this custom resource with Kubernetes.

        Assumes that the Kubernetes client is already configured.
        """
        api = kubernetes.client.ApiextensionsV1Api()
        crd = self.make_crd()
        crd_name = crd['metadata']['name']
        try:
            api.read_custom_resource_definition(crd_name)
        except kubernetes.client.rest.ApiException as exc:
            if exc.status != 404:
                raise
            api.create_custom_resource_definition(crd)
        else:
            api.patch_custom_resource_definition(crd_name, crd)

    def subresource_labels(self, *, name = None, component = None):
        """
        Return the labels required to identify a Kubernetes resource as a subresource of
        this custom resource.
        
        Optionally, a specific instance and/or component can be specified.
        """
        labels = { "app.kubernetes.io/name": self.singular_name }
        if name:
            labels["app.kubernetes.io/instance"] = name
        if component:
            labels["app.kubernetes.io/component"] = component
        return labels

    def subresource_label_selector(self, **kwargs):
        """
        Return a label selector that can be used with the Kubernetes client to select only
        resources that are subresources of this custom resource.
        
        Optionally, a specific instance and/or component can be specified.
        """
        return ",".join(
            f"{label}={value}"
            for label, value in self.subresource_labels(**kwargs).items()
        )

    def get_owner_instance(self, subresource):
        """
        Returns the instance of this custom resource that owns the given subresource or
        none if the instance does not exist.

        This uses the labels of the given object rather than owner references as this allows
        indirect subresources, e.g. pods of deployments owned by the instance, to be resolved
        correctly.
        """
        api = kubernetes.client.CustomObjectsApi()
        return api.get_namespaced_custom_object(
            self.group,
            self.current_version.name,
            subresource['metadata']['namespace'],
            self.plural_name,
            subresource['metadata']['labels']["app.kubernetes.io/instance"]
        )

    def apply_patch(self, namespace, name, patch):
        """
        Applies the given patch to the specified instance of this custom resource.
        """
        api = kubernetes.client.CustomObjectsApi()
        api.patch_namespaced_custom_object(
            self.group,
            self.current_version.name,
            namespace,
            self.plural_name,
            name,
            patch
        )

    def on_create(self, **kwargs):
        """
        Returns a decorator that registers the decorated function as a kopf create hook
        for this custom resource.
        """
        return kopf.on.create(self.group, self.current_version.name, self.plural_name, **kwargs)

    def on_delete(self, **kwargs):
        """
        Returns a decorator that registers the decorated function as a kopf delete hook
        for this custom resource.
        """
        return kopf.on.delete(self.group, self.current_version.name, self.plural_name, **kwargs)

    def on_update(self, **kwargs):
        """
        Returns a decorator that registers the decorated function as a kopf update hook
        for this custom resource.

        Optionally, a trigger field can be specified with an optional trigger value.
        """
        return kopf.on.update(self.group, self.current_version.name, self.plural_name, **kwargs)

    def on_subresource_event(self, *args, component = None, **kwargs):
        """
        Returns a decorator that registers the decorated function as a kopf event hook
        for resources of the given group/version/kind that are also subresources of an
        instance of this custom resource. Optionally, a specific component can also
        be given.

        This is acheived by filtering the subresources based on the labels for this
        custom resource.
        """
        labels = kwargs.pop('labels', {})
        labels.update(self.subresource_labels(component = component))
        return kopf.on.event(*args, labels = labels, **kwargs)
