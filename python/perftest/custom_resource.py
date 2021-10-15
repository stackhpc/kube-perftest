import functools
import inspect

import jinja2
import kopf
import kubernetes
import yaml


class CustomResource:
    """
    Class for defining a custom resource.
    """
    @classmethod
    def initialise_from_template(cls, template, env = None):
        """
        Returns a custom resource object that uses the given template as a source.

        This assumes that the calling module has a "templates" directory alongside it.
        This behaviour can be overridden by passing a template environment.
        """
        if not env:
            # Assume that the module containing the calling code is a submodule
            # of the module containing the templates directory
            frame = inspect.stack()[1][0]
            module = inspect.getmodule(frame)
            loader = jinja2.PackageLoader(module.__name__.rsplit(".", maxsplit = 1)[0])
            env = jinja2.Environment(loader = loader, autoescape = False)
        # Render the given template and extract the result as YAML
        crd_definition = yaml.safe_load(env.get_template(template).render())
        # Initialise and return a custom resource object
        resource = cls(
            crd_definition["spec"]["group"],
            next(
                v["name"]
                for v in crd_definition["spec"]["versions"]
                if v["storage"]
            ),
            crd_definition["spec"]["names"]["kind"],
            crd_definition["spec"]["names"]["plural"],
            crd_definition["spec"]["names"].get("singular"),
            env
        )
        # Register a kopf startup hook to register the CRD
        def register_crd(**kwargs):
            kopf.login_via_client(**kwargs)
            # Create or update the CRD in the target cluster
            apiextensionsv1 = kubernetes.client.ApiextensionsV1Api()
            crd_name = crd_definition["metadata"]["name"]
            try:
                apiextensionsv1.read_custom_resource_definition(crd_name)
            except kubernetes.client.rest.ApiException as exc:
                if exc.status != 404:
                    raise
                apiextensionsv1.create_custom_resource_definition(crd_definition)
            else:
                apiextensionsv1.patch_custom_resource_definition(crd_name, crd_definition)
        kopf.on.startup()(register_crd)
        return resource       

    def __init__(
        self,
        group,
        version,
        kind,
        plural_name,
        singular_name,
        env
    ):
        self.group = group
        self.version = version
        self.kind = kind
        self.plural_name = plural_name
        self.singular_name = singular_name or self.kind.lower()
        self.env = env
        # Register a filter that converts the given object to YAML
        self.env.filters["toyaml"] = yaml.safe_dump
        # Register a template function for rendering subresource labels
        def subresource_labels(name = None, component = None):
            return yaml.safe_dump(self.subresource_labels(name = name, component = component))
        self.env.globals["subresource_labels"] = subresource_labels
        # Also register a function that produces match expressions for subresource labels for
        # use in pod [anti]affinity rules
        def match_expressions(name = None, component = None):
            labels = self.subresource_labels(name = name, component = component)
            return yaml.safe_dump([
                dict(key = label, operator = "In", values = [value])
                for label, value in labels.items()
            ])
        self.env.globals["match_expressions"] = match_expressions        

    @property
    def full_name(self):
        """
        The full name of the custom resource.
        """
        return f"{self.plural_name}.{self.group}"

    def from_template(self, template, **kwargs):
        """
        Renders the given template with the given kwargs, loads the result as YAML and returns it.
        """
        return yaml.safe_load(self.env.get_template(template).render(**kwargs))

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

    def apply_patch(self, namespace, name, patch):
        """
        Applies the given patch to the specified instance of this custom resource.
        """
        api = kubernetes.client.CustomObjectsApi()
        api.patch_namespaced_custom_object(
            self.group,
            self.version,
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
        return kopf.on.create(self.group, self.version, self.plural_name, **kwargs)

    def on_delete(self, **kwargs):
        """
        Returns a decorator that registers the decorated function as a kopf delete hook
        for this custom resource.
        """
        return kopf.on.delete(self.group, self.version, self.plural_name, **kwargs)

    def on_update(self, **kwargs):
        """
        Returns a decorator that registers the decorated function as a kopf update hook
        for this custom resource.

        Optionally, a trigger field can be specified with an optional trigger value.
        """
        return kopf.on.update(self.group, self.version, self.plural_name, **kwargs)

    def on_subresource_event(self, *args, component = None, **kwargs):
        """
        Returns a decorator that registers the decorated function as a kopf event hook
        for resources of the given group/version/kind that are also subresources of an
        instance of this custom resource. Optionally, a specific component can also
        be given.

        This is acheived by filtering the subresources based on the labels for this
        custom resource.
        """
        labels = kwargs.pop("labels", {})
        labels.update(self.subresource_labels(component = component))
        return kopf.on.event(*args, labels = labels, **kwargs)

    def on_owned_resource_event(self, *args, **kwargs):
        """
        Returns a decorator that registers the decorated function as a kopf event hook
        for resources of the given group/version/kind that have an instance of this
        custom resource as an owner.

        The owner is passed to the decorated function as the 'owner' kwarg.
        """
        def decorator(fn):
            @functools.wraps(fn)
            def handler(**inner):
                # Try to find an owner that has the same kind as this custom resource
                metadata = inner["meta"]
                try:
                    name = next(
                        owner["name"]
                        for owner in metadata.get("ownerReferences", [])
                        if (
                            owner["apiVersion"].startswith(self.group) and
                            owner["kind"] == self.kind
                        )
                    )
                except StopIteration:
                    # If there is no owner of this type, do nothing
                    return
                # Next, try to actually fetch the instance
                api = kubernetes.client.CustomObjectsApi()
                try:
                    owner = api.get_namespaced_custom_object(
                        self.group,
                        self.version,
                        metadata["namespace"],
                        self.plural_name,
                        name
                    )
                except kubernetes.client.rest.ApiException as exc:
                    # If the instance is not found, do nothing
                    if exc.status == 404:
                        return
                    else:
                        raise
                return fn(owner = owner, **inner)
            return kopf.on.event(*args, **kwargs)(handler)
        return decorator
