import functools
import math
import re
import typing as t
from kube_custom_resource import schema
from pydantic import Field, confloat
from .errors import PodLogFormatError


def mergeconcat(
    defaults: t.Dict[t.Any, t.Any],
    *overrides: t.Dict[t.Any, t.Any]
) -> t.Dict[t.Any, t.Any]:
    """
    Returns a new dictionary obtained by deep-merging multiple sets of overrides
    into defaults, with precedence from right to left.
    """
    def mergeconcat2(defaults, overrides):
        if isinstance(defaults, dict) and isinstance(overrides, dict):
            merged = dict(defaults)
            for key, value in overrides.items():
                if key in defaults:
                    merged[key] = mergeconcat2(defaults[key], value)
                else:
                    merged[key] = value
            return merged
        elif isinstance(defaults, (list, tuple)) and isinstance(overrides, (list, tuple)):
            merged = list(defaults)
            merged.extend(overrides)
            return merged
        else:
            return overrides if overrides is not None else defaults
    return functools.reduce(mergeconcat2, overrides, defaults)


def check_condition(obj: t.Dict[str, t.Any], name: str) -> bool:
    """
    Returns True if the specified condition exists and is True for the given object,
    False otherwise.
    """
    return any(
        condition["type"] == name and condition["status"] == "True"
        for condition in obj.get("status", {}).get("conditions", [])
    )


_PREFIXES = ("", "K", "M", "G", "T", "P", "E", "Z", "Y")

def format_amount(
    amount,
    original_prefix = "",
    /,
    quotient = 1024,
    prefixes = _PREFIXES
):
    """
    Formats an amount by increasing the prefix of the units when it is possible to do so.

    Returns a tuple of (formatted_amount, prefix) to be used.
    """
    # If the amount is zero, then use the original prefix
    if amount == 0:
        return (str(int(amount)), original_prefix)
    # Otherwise calculate the exponent and the formatted amount
    exponent = math.floor(math.log(amount) / math.log(quotient))
    new_amount = (amount / math.pow(quotient, exponent))
    # Make sure the new amount renders nicely for integers, e.g. 1GB vs 1.00GB
    if new_amount % 1 == 0:
        formatted_amount = str(int(new_amount))
    else:
        integer_part = int(new_amount)
        fractional_part = new_amount - integer_part
        # Format the fractional part to two significant figures and remove the "0."
        fractional_part = f"{fractional_part:.2g}"[2:]
        formatted_amount = f"{integer_part}.{fractional_part}"
    prefix_index = prefixes.index(original_prefix) + exponent
    return (formatted_amount, prefixes[prefix_index])


GNU_TIME_EXTRACTION_REGEX = re.compile(
    r"\s*Command being timed:\s+\"(?P<command>.+)\""
    r"\s+User time \(seconds\):\s+(?P<user_time>\d+\.\d+)"
    r"\s+System time \(seconds\):\s+(?P<sys_time>\d+\.\d+)"
    r"\s+Percent of CPU this job got:\s+(?P<cpu_percentage>\d+)\%"
    r"\s+Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s+(?P<wall_time>\d*:*\d+:\d+\.\d+)"
)

class GnuTimeResult(schema.BaseModel):
    """
    Helper class for parsing the output of the gnu time wrapper. Example output
    from (verbose mode) `/usr/bin/time -v`:
        Command being timed: "sleep 2"
        User time (seconds): 0.00
        System time (seconds): 0.00
        Percent of CPU this job got: 0%
        Elapsed (wall clock) time (h:mm:ss or m:ss): 0:02.00
        Average shared text size (kbytes): 0
        Average unshared data size (kbytes): 0
        Average stack size (kbytes): 0
        Average total size (kbytes): 0
        Maximum resident set size (kbytes): 1612
        Average resident set size (kbytes): 0
        Major (requiring I/O) page faults: 0
        Minor (reclaiming a frame) page faults: 67
        Voluntary context switches: 2
        Involuntary context switches: 0
        Swaps: 0
        File system inputs: 0
        File system outputs: 0
        Socket messages sent: 0
        Socket messages received: 0
        Signals delivered: 0
        Page size (bytes): 4096
        Exit status: 0
    """
    # Add other fields here as needed
    command: str = Field(description="The command being timed.")
    user_time_secs: confloat(ge=0) = Field(description="The time spent executing user space code.")
    sys_time_secs: confloat(ge=0) = Field(description="The time spent executing system (kernel space) code.")
    cpu_percentage: confloat(ge=0) = Field(description="The (peak) percentage of CPU used.")
    wall_time_secs: confloat(ge=0) = Field(description="The wall clock time for this benchmark run.")
        
    @classmethod
    def parse(cls, input: str):
        match = GNU_TIME_EXTRACTION_REGEX.search(input)
        if not match:
            raise PodLogFormatError("failed to parse output of GNU time command")
        
        # Convert wall time to seconds for consistency with other fields
        # Default format is either 'hh:mm:ss.ss' or 'mm:ss.ss' depending on value
        wall_time = match.group("wall_time")
        try:
            hrs_mins_secs, frac_secs = wall_time.split(".")
            parts = hrs_mins_secs.split(":")
            if len(parts) == 2:
                hrs, mins, secs = 0, *parts
            elif len(parts) == 3:
                hrs, mins, secs = parts
            wall_time_secs = float(hrs)*3600 + float(mins)*60 + float(secs) + float("0."+frac_secs)
        except:
            raise PodLogFormatError("failed to parse GNU wall time in format hh:mm:ss.ss or mm:ss.ss")

        return GnuTimeResult(
            command = match.group("command"),
            user_time_secs = match.group("user_time"),
            sys_time_secs = match.group("sys_time"),
            cpu_percentage = match.group("cpu_percentage"),
            wall_time_secs = wall_time_secs,
        )
