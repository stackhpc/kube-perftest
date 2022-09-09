import datetime
import itertools
import math
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


class BenchmarkSetPermutations(schema.BaseModel):
    """
    Defines the permutations to use for the benchmarks in the set.
    """
    product: schema.Dict[str, t.List[schema.Any]] = Field(
        default_factory = dict,
        description = (
            "Permutations are generated using the cross-product of the given keys/values."
        )
    )
    explicit: t.List[schema.Dict[str, t.Any]] = Field(
        default_factory = list,
        description = "A list of explicit permutations to use."
    )

    def get_count(self) -> int:
        """
        Returns the number of permutations for the benchmark set.
        """
        product_count = (
            math.prod(len(vs) for vs in self.product.values())
            if self.product
            else 0
        )
        return product_count + len(self.explicit)

    def get_permutations(self) -> t.Iterable[t.Dict[str, t.Any]]:
        """
        Returns all the permutations for the benchmark set.
        """
        if self.product:
            yield from (
                dict(permutation)
                for permutation in itertools.product(*(
                    [(k, v) for v in vs]
                    for k, vs in self.product.items()
                ))
            )
        yield from self.explicit


class BenchmarkSetSpec(schema.BaseModel):
    """
    Defines the parameters for a benchmark set.
    """
    template: BenchmarkSetTemplate = Field(
        ...,
        description = "The template to use for the benchmarks."
    )
    permutations: BenchmarkSetPermutations = Field(
        default_factory = dict,
        description = "The permutations to use for the benchmarks."
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
            "name": "Failed",
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
