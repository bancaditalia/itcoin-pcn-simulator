import argparse
import decimal
import functools
import json
import logging
import math
import re
from collections.abc import Callable
from importlib import metadata
from pathlib import Path
from typing import Optional

import networkx as nx
from numpy.random import default_rng

"""Exit codes"""
EXIT_SUCCESS = 0
EXIT_FAILURE = 1

EU_COUNTRY_CODE = "EU"

FLOAT_REGEX_PATTERN = r"[0-9]+\.[0-9]+"


def string_represents_float(n):
    try:
        float(n)
        return True
    except ValueError:
        return False


def string_represents_integer(n):
    try:
        float(n)
    except ValueError:
        return False
    else:
        return ("." not in n) and float(n).is_integer()


def string_to_typed_value(s):
    return (
        True
        if (s.lower() == "true")
        else (
            False
            if (s.lower() == "false")
            else (
                int(s)
                if string_represents_integer(s)
                else float(s)
                if string_represents_float(s)
                else s
            )
        )
    )


def idx_to_alphabetical(idx):
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    n = len(alphabet)
    return ("" if idx < n else idx_to_alphabetical(math.floor(idx / n) - 1)) + alphabet[
        idx % n
    ]


def decode(value_as_string):
    multiple_symbol_to_multiple_factor = {
        "K": 10**3,
        "M": 10**6,
        "B": 10**9,
        "C": 10.0 ** (-2),
        "CENT": 10.0 ** (-2),
        "CENTS": 10.0 ** (-2),
        "%": 10.0 ** (-2),
    }
    for symbol, factor in multiple_symbol_to_multiple_factor.items():
        if value_as_string.upper().endswith(symbol):
            value = float(value_as_string[: -len(symbol)]) * factor
            return (
                int(value) if isinstance(value, float) and value.is_integer() else value
            )
    return string_to_typed_value(
        value_as_string,
    )  # int(number_as_string) if string_represents_integer(number_as_string) else float(number_as_string)


def eu(number_as_string):
    return float(decode(number_as_string))


def float_round(value, number_of_digits=2, direction="closer"):
    scale_factor = 10**number_of_digits
    return {
        "up": lambda v: math.ceil(scale_factor * v) / (1.0 * scale_factor),
        "down": lambda v: math.floor(scale_factor * v) / (1.0 * scale_factor),
        "closer": lambda v: round(scale_factor * v) / (1.0 * scale_factor),
    }[direction](value)


def flatten_attribute_names(nested_attr_dict, prefix=""):
    if not isinstance(nested_attr_dict, dict):
        return {prefix: nested_attr_dict}

    def _extend(prefix, key):
        return (prefix + "_" if len(prefix) > 0 else "") + key

    flat_dict = {}
    for key, value in nested_attr_dict.items():
        if isinstance(key, str):
            if key[:1] == "[" and key[-1:] == "]":
                flat_dict[key] = flatten_attribute_names(value, prefix=prefix)
            else:
                flat_dict.update(
                    flatten_attribute_names(value, prefix=_extend(prefix, key)),
                )
        elif isinstance(key, tuple):
            flat_dict[tuple([_extend(prefix, elem) for elem in list(key)])] = value
        else:
            print("??")
            exit(-1)
    return flat_dict


def inject_custom_param_value(model, keypath, value):
    head_tail = keypath.split("->", 1)
    key = int(head_tail[0]) if string_represents_integer(head_tail[0]) else head_tail[0]
    if len(head_tail) == 1:
        model[key] = (
            int(value)
            if string_represents_integer(value)
            else float(value)
            if string_represents_float(value)
            else value
        )
    else:
        inject_custom_param_value(model[key], head_tail[1], value)


class Δ(float):
    param2value = {}

    def __new__(cls, label):
        cls.param_label = label
        return float.__new__(cls, 0.0)

    def __gt__(self, a):
        return self.param2value.get(self.param_label, a)


def fake_demo_friendly_name_for_node_with_label(label):
    match = re.match(r"([a-z]+)([0-9]+)", label, re.I)
    if match:
        (node_type, node_index_as_str) = match.groups()
        node_index = int(node_index_as_str) - 1
        _fake_names = {
            "CB": ["Plasma CB"],
            "Intermediary": ["SpringBank", "SkyBancorp"],
            "Retail": [
                "Alice",
                "Bob",
                "Charlie",
                "Daniel",
                "Emily",
                "Frank",
                "Gustave",
            ],
            "Unbanked": ["Joe (unbanked)", "Eve (unbanked)"],
        }

        def build_name_out_of_list(name_list, index):
            cycle = int(int(index) / len(name_list))
            suffix = str(1 + cycle) if cycle > 0 else ""
            return name_list[index % len(name_list)] + suffix

        return build_name_out_of_list(_fake_names[node_type], node_index)

    return label


def demoize_node_names(g):
    standard_names = g.nodes()
    demo_names = [
        fake_demo_friendly_name_for_node_with_label(name) for name in standard_names
    ]
    name_mapping = dict(zip(standard_names, demo_names, strict=False))
    return nx.relabel_nodes(g, name_mapping)


def import_networkx_type(network_type: str) -> type[nx.Graph]:
    """Import the networkx type from a string."""
    match network_type:
        case "DiGraph":
            return nx.DiGraph
        case "Graph":
            return nx.Graph
        case "MultiDiGraph":
            return nx.MultiDiGraph
        case "MultiGraph":
            return nx.MultiGraph
        case _:
            msg = f"Unknown network type: {network_type}"
            raise ValueError(msg)


def get_version() -> str:
    """Return the version."""
    return metadata.version("python-utils")


def str_to_integer(s: str, check: Callable[[int], bool], error_msg: str) -> int:
    """Parse and check the given integer."""
    try:
        result = int(s)
    except ValueError:
        msg = f"{s} is not an integer"
        raise argparse.ArgumentTypeError(msg) from None
    if not check(result):
        msg = f"{result} is not valid: {error_msg}"
        raise argparse.ArgumentTypeError(msg)
    return result


check_nonnegative_integer = functools.partial(
    str_to_integer,
    check=lambda i: i >= 0,
    error_msg="must be nonnegative",
)
check_positive_integer = functools.partial(
    str_to_integer,
    check=lambda i: i > 0,
    error_msg="is not greater than 0",
)


def integer_in_human_format(value_as_string: str) -> int:
    """Parse and check the given integer in human format."""
    decoded: int
    try:
        decoded = decode(value_as_string)
    except ValueError:
        msg = f"{value_as_string} is not a valid integer in human format"
        raise argparse.ArgumentTypeError(msg) from None
    return check_positive_integer(decoded)


def network_size_string(s: str) -> tuple[int, int, int, int]:
    """Parse and check the given network size string.

    A 'network size' string specifies the size of each node type set in the network.
    It is of the following form:

        <CB-size> <Intermediary-size> <Retail-size> <Merchant-size>
    """
    try:
        sizes = s.split()
        assert len(sizes) == 4, "the network size string must be of 4 integers"
        human_format_sizes = map(integer_in_human_format, sizes)
        return tuple(human_format_sizes)  # type: ignore
    except AssertionError as e:
        msg = f"{s} is not a valid network size string: {e}"
        raise argparse.ArgumentTypeError(msg) from None


def optional(param_parser: Callable) -> Callable | None:
    """Return a parser that can parse the given parser or None."""

    @functools.wraps(param_parser)
    def optional_parser(s: str) -> Optional:
        try:
            return param_parser(s)
        except ValueError:
            return None

    return optional_parser


def nonnegative_float(arg: str) -> float:
    """Check that the given float is nonnegative."""
    try:
        result = float(arg)
    except ValueError:
        msg = f"{arg} is not a float"
        raise argparse.ArgumentTypeError(msg) from None
    if result < 0.0:
        msg = f"{arg} is negative"
        raise argparse.ArgumentTypeError(msg)
    return result


def float_between_range(
    arg: str,
    lower: float,
    upper: float,
    lower_is_strict: bool,
    upper_is_strict: bool,
) -> float:
    """Check that the given float is between the given range."""
    try:
        result = float(arg)
    except ValueError:
        msg = f"{arg} is not a float"
        raise argparse.ArgumentTypeError(msg) from None

    def is_big_enough(x):
        return x > lower if lower_is_strict else x >= lower

    def is_small_enough(x):
        return x < upper if upper_is_strict else x <= upper

    if not is_big_enough(result) or not is_small_enough(result):
        strict_str = "(strict)"
        msg = (
            f"{arg} is not between {lower} {strict_str if lower_is_strict else ''} and {upper} "
            f"{strict_str if upper_is_strict else ''}"
        )
        raise argparse.ArgumentTypeError(msg)
    return result


float_between_0_and_1 = functools.partial(
    float_between_range,
    lower=0.0,
    upper=1.0,
    lower_is_strict=False,
    upper_is_strict=False,
)

capacity_fraction = float_between_0_and_1


def nonempty_string(s: str) -> str:
    """Check that the given string is not empty."""
    if not s:
        msg = "must be a non-empty string"
        raise argparse.ArgumentTypeError(msg)
    return s


def load_json(input_file: Path) -> dict:
    """Load a JSON file, given its path."""
    with input_file.open() as file:
        return json.load(file)


class SupportedNetworkxFormatter(argparse.Action):
    """Check that the given formatter is supported by Networkx."""

    SUPPORTED_FORMATTERS = tuple(
        sorted(
            [
                name.split("_", 1)[1]
                for name in dir(nx)
                if name.startswith("write_") and callable(getattr(nx, name))
            ],
        ),
    )

    def __call__(self, parser, namespace, values, option_string=None):
        formatter = values
        if not hasattr(nx, f"write_{formatter}"):
            msg = f"{formatter} is not a supported formatter; choose one of {self.SUPPORTED_FORMATTERS}"
            raise argparse.ArgumentTypeError(msg)
        networkx_function = getattr(nx, f"write_{formatter}")
        setattr(namespace, self.dest, networkx_function)


def check_file_exists(
    filepath: Path,
    exception_class: type[Exception] = ValueError,
) -> None:
    """Check if the file exists.

    Args:
    ----
        input_file: The path to the file.
        exception_class: The exception class to be raised if validation fails.
    """
    if not filepath.is_file():
        msg = f"file {filepath} does not exist"
        raise exception_class(msg)


def check_file_is_file(
    filepath: Path,
    exception_class: type[Exception] = ValueError,
) -> None:
    """Check if the path points to a file.

    Args:
    ----
        filepath: The path to the input file.
        exception_class: The exception class to be raised if validation fails.
    """
    if not filepath.is_file():
        msg = f"Input file {filepath} is not a file"
        raise exception_class(msg)


def check_path_is_directory(
    dirpath: Path,
    exception_class: type[Exception] = ValueError,
) -> None:
    """Check if the directory exists and is a directory.

    Args:
    ----
        dirpath: The path to the output directory.
        exception_class: The exception class to be raised if validation fails.
    """
    if not dirpath.is_dir():
        msg = f"path {dirpath} does not exist or is not a directory. Please create it"
        raise exception_class(msg)


def check_dir_is_empty(
    dirpath: Path,
    exception_class: type[Exception] = ValueError,
) -> None:
    """Check if the output directory is empty.

    It assumes the path exists and is a directory.

    Args:
    ----
        output_dir: The path to the directory.
        exception_class: The exception class to be raised if validation fails.
    """
    assert dirpath.is_dir()
    if len(list(dirpath.iterdir())) > 0:
        msg = f"directory {dirpath} is not empty. Please empty it or choose another one"
        raise exception_class(msg)


def set_of_strings(s: str, pattern: str = r"[A-Z]+") -> set[str]:
    """Parse and check the given set of strings.

    A 'set of strings' is a comma-separated list of strings.
    """
    token_regex = re.compile(pattern)
    tokens = re.split(r"\s*,\s*", s)
    if len(tokens) == 0:
        msg = f"{s} is not a valid set of strings: it is empty"
        raise argparse.ArgumentTypeError(msg)

    seen = set()
    for token in map(str.strip, tokens):
        if not token_regex.fullmatch(token):
            msg = f"{s} is not a valid set of strings: {token} does not match regex {pattern}"
            raise argparse.ArgumentTypeError(msg)
        if token in seen:
            msg = f"{s} is not a valid set of strings: {token} appears more than once"
            raise argparse.ArgumentTypeError(msg)
        seen.add(token)

    return seen


def configure_logging(verbose: bool) -> None:
    """Configure logging.

    Args:
    ----
        verbose: if True, set the logging level to DEBUG, otherwise to INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s][%(levelname)-5s][%(filename)s:%(lineno)-3s] %(message)s",
    )


def try_is_weakly_connected(subnetwork) -> bool | None:
    """Try to check if the given subnetwork is weakly connected."""
    try:
        return nx.is_weakly_connected(subnetwork)
    except nx.NetworkXPointlessConcept:
        return None


def try_is_strongly_connected(subnetwork) -> bool | None:
    """Try to check if the given subnetwork is strongly connected."""
    try:
        return nx.is_strongly_connected(subnetwork)
    except nx.NetworkXPointlessConcept:
        return None


def float_to_str_with_decimals(f):
    """Convert the given float to a string, without resorting to scientific notation (as the builtin str does).

    As a simplifying assumption, it assumes a maximum of 20 digits after comma.
    """
    ctx = decimal.Context()
    # 20 digits should be
    ctx.prec = 20
    float_repr = repr(f)
    assert len(float_repr) < 20, f"float {f} has more than 20 digits"
    d1 = ctx.create_decimal(repr(f))
    return format(d1, "f")


def nb_digits_after_comma(number: float) -> int:
    """Return the number of digits after the comma of the given float."""
    return len(float_to_str_with_decimals(number).split(".")[1])


def fraction_format_str(number: float, max_nb_digits: int) -> str:
    """Return the fraction format string of the given float."""
    return f"%0{max_nb_digits}.{max_nb_digits}f" % number


class SeedGenerator:
    """A generator of seeds for random number generators."""

    def __init__(self, seed: int | None = None):
        """Initialize the seed generator."""
        self._seed = seed
        self._rng = default_rng(seed)

    def next_seed(self) -> int:
        """Generate a new seed.

        This method does side-effect since it changes the state of the RNG.
        """
        return int(self._rng.integers(0, 2**32 - 1))
