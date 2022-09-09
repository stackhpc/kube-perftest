import datetime
import typing as t

from pydantic import Field, constr

from kube_custom_resource import CustomResource, schema

from ...config import settings


class BenchmarkSetTemplate(schema.BaseModel):
    """
    Defines the shape of a template for a benchmark set.
    """
    api_version: constr(regex = r"^" + settings.api_group) = Field(
        ...,
        description = "The API version of the benchmark to create."
    )
    kind: constr(min_length = 1) = Field(
        ...,
        description = "The kind of the benchmark to create."
    )
    spec: schema.Dict[str, t.Any] = Field(
        default_factory = dict,
        description = "The fixed part of the spec for the benchmark."
    )


class BenchmarkSetSpec(schema.BaseModel):
    """
    Defines the parameters for a benchmark set.
    """
    template: BenchmarkSetTemplate = Field(
        ...,
        description = "The template to use for the benchmarks."
    )
    permutations: schema.Dict[str, t.List[schema.Any]] = Field(
        default_factory = dict,
        description = (
            "The permutations to use for the benchmarks. "
            "The given keys and values will be used in a cross-product."
        )
    )


class BenchmarkSetStatus(schema.BaseModel):
    """
    Represents the status of a benchmark set.
    """
    count: t.Optional[schema.conint(ge = 0)] = Field(
        None,
        description = "The number of benchmarks in the set."
    )
    completed: schema.Dict[str, bool] = Field(
        default_factory = dict,
        description = (
            "Map of completed benchmark names to a boolean indicating whether the "
            "benchmark was successful or not."
        )
    )
    succeeded: t.Optional[schema.conint(ge = 0)] = Field(
        None,
        description = "The number of benchmarks that have completed successfully."
    )
    failed: t.Optional[schema.conint(ge = 0)] = Field(
        None,
        description = "The number of benchmarks that have failed."
    )
    finished_at: t.Optional[datetime.datetime] = Field(
        None,
        description = "The time at which the benchmark finished."
    )


class BenchmarkSet(
    CustomResource,
    subresources = {"status": {}},
    printer_columns = [
        {
            "name": "Count",
            "type": "string",
            "jsonPath": ".status.count",
        },
        {
            "name": "Succeeded",
            "type": "string",
            "jsonPath": ".status.succeeded",
        },
        {
            "name": "Count",
            "type": "string",
            "jsonPath": ".status.failed",
        },
        {
            "name": "Finished",
            "type": "date",
            "jsonPath": ".status.finishedAt",
        },
    ]
):
    """
    Custom resource for a parameterised set of benchmarks.
    """
    spec: BenchmarkSetSpec = Field(
        ...,
        description = "The spec for the benchmark set."
    )
    status: BenchmarkSetStatus = Field(
        default_factory = BenchmarkSetStatus,
        description = "The status of the benchmark set."
    )
