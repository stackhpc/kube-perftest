import json
import typing as t

import jinja2

from pydantic.json import pydantic_encoder

import yaml

from . import utils


class Loader:
    """
    Class for returning objects created by rendering YAML templates from this package.
    """
    def __init__(self, **globals):
        # We have two environments
        # One has access to the package templates
        loader = jinja2.PackageLoader(self.__module__.rsplit(".", maxsplit = 1)[0])
        self._env = self._create_env(loader, **globals)
        # One can only be used to render strings
        self._safe_env = self._create_env(jinja2.BaseLoader(), **globals)

    def _create_env(self, loader, **globals):
        """
        Creates an environment with the given loader.
        """
        env = jinja2.Environment(loader = loader, autoescape = False)
        env.globals.update(globals)
        env.filters.update(
            mergeconcat = utils.mergeconcat,
            fromyaml = yaml.safe_load,
            # In order to benefit from correct serialisation of Pydantic models,
            # we go via JSON to YAML
            toyaml = lambda obj: yaml.safe_dump(
                json.loads(
                    json.dumps(
                        obj,
                        default = pydantic_encoder
                    )
                )
            )
        )
        return env

    def render_string(
        self,
        template_str: str,
        /,
        _safe: bool = True,
        **params: t.Any
    ) -> str:
        """
        Render the given template string with the given params and return the result as
        a string.

        By default, this uses the safe environment which does not have access to templates.
        """
        env = self._safe_env if _safe else self._env
        return env.from_string(template_str).render(**params)

    def yaml_string(
        self,
        template_str: str,
        /,
        _safe: bool = True,
        **params: t.Any
    ) -> t.Dict[str, t.Any]:
        """
        Render the given template string with the given params, parse the result as YAML
        and return the resulting object.
        """
        return yaml.safe_load(self.render_string(template_str, _safe = _safe, **params))

    def yaml_string_all(
        self,
        template_str: str,
        /,
        _safe: bool = True,
        **params: t.Any
    ) -> t.Dict[str, t.Any]:
        """
        Render the given template string with the given params, parse the result as YAML
        and return the resulting objects.
        """
        return yaml.safe_load_all(self.render_string(template_str, _safe = _safe, **params))

    def render_template(self, template: str, **params: t.Any) -> str:
        """
        Render the specified template with the given params and return the result as a string.
        """
        return self._env.get_template(template).render(**params)

    def yaml_template(self, template: str, **params: t.Any) -> t.Dict[str, t.Any]:
        """
        Render the specified template with the given params, parse the result as YAML and
        return the resulting object.
        """
        return yaml.safe_load(self.render_template(template, **params))

    def yaml_template_all(self, template: str, **params: t.Any) -> t.Dict[str, t.Any]:
        """
        Render the specified template with the given params, parse the result as YAML and
        return the resulting objects.
        """
        return yaml.safe_load_all(self.render_template(template, **params))
