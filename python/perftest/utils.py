import functools
import math
import typing as t


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
