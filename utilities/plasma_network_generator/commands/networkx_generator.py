"""The generator script."""

import argparse
import dataclasses
import logging
import pprint
import sys
from collections.abc import Callable
from pathlib import Path
from textwrap import dedent, indent
from unittest.mock import patch

import networkx as nx
import numpy as np

from plasma_network_generator.core import (
    NationSpec,
    NationSpecs,
    NodeType,
    get_eurosystem_nation_specs,
)
from plasma_network_generator.dump import (
    dump_info_about_layeers_and_nodes,
    dump_info_about_network_random_models,
    dump_network_analysis,
    dump_plasma_network,
)
from plasma_network_generator.exceptions import CliArgsValidationError
from plasma_network_generator.generation import (
    generate_plasma_network,
    postprocess_plasma_network,
)
from plasma_network_generator.model import payment_subnetworks_random_models
from plasma_network_generator.params import (
    infer_missing_rnd_model_params,
)
from plasma_network_generator.utils import (
    EXIT_FAILURE,
    EXIT_SUCCESS,
    SupportedNetworkxFormatter,
    check_dir_is_empty,
    check_file_exists,
    check_nonnegative_integer,
    check_path_is_directory,
    check_positive_integer,
    configure_logging,
    demoize_node_names,
    flatten_attribute_names,
    float_between_0_and_1,
    get_version,
    inject_custom_param_value,
    integer_in_human_format,
    load_json,
    network_size_string,
    nonnegative_float,
    set_of_strings,
)

DEFAULT_INPUT_FILE = Path("defaultCapacities.json")
DEFAULT_OUTPUT_DIR = Path("output")
DEFAULT_OUTPUT_FORMATTER = "gml"
DEFAULT_RANDOM_SEED: int | None = None
DEFAULT_DUMP_NETWORK: bool = True
DEFAULT_DUMP_SUBNETWORKS: bool = False
DEFAULT_SUBNETWORK_FILTER: str | None = None
DEFAULT_FAKE_DEMO_NAMES: bool = False
DEFAULT_DEPLOY_NODE_COUNT: int = 1
DEFAULT_UNIQUE_CB: bool = False
DEFAULT_NATIONS: NationSpecs = get_eurosystem_nation_specs()

NETWORK_OUTPUT_FILENAME = Path("network")


@dataclasses.dataclass(frozen=True)
class RndModel:
    """Data class to store random model parameters.

    This class should be initialized via RndModel.initialize_from_cli_args, which will
    initialize the parameters from command line arguments using the legacy argument parser.
    By doing so, the parameters will be completed with the missing ones, and their consistency will be guaranteed.

    It is unlikely that this class will be used directly, but it is convenient so to isolate the random model
    parameters in the script implementation.

    Use the command line argument --help to get a list of the supported arguments.
    """

    number_of_nodes_in_simulation: int
    number_of_CBs_in_simulation: int
    number_of_intermediaries_in_simulation: int
    number_of_retail_users_in_simulation: int
    number_of_merchants_in_simulation: int
    citizens_to_intermediary_ratio: float
    intermediary_to_CB_ratio: float
    citizens_to_CB_ratio: float
    merchants_to_retail_users_ratio: float
    number_of_banked_retail_users_in_simulation: int
    number_of_unbanked_retail_users_in_simulation: int
    fraction_of_unbanked_retail_users: float
    p_small_merchants: float
    p_medium_merchants: float
    p_large_merchants: float
    unique_cb: bool
    nations: NationSpecs

    def asdict(self) -> dict:
        """Get a dictionary representation of the random model parameters."""
        return {
            "number_of_nodes_in_simulation": self.count_by_nation_name(
                self.number_of_nodes_in_simulation,
            ),
            "number_of_CBs_in_simulation": self.cb_count_by_nation_name(),
            "number_of_intermediaries_in_simulation": self.intermediary_counts_by_nation_name(),
            "number_of_retail_users_in_simulation": self.count_by_nation_name(
                self.number_of_retail_users_in_simulation,
            ),
            "number_of_merchants_in_simulation": self.count_by_nation_name(
                self.number_of_merchants_in_simulation,
            ),
            "number_of_small_merchants_in_simulation": self.merchant_counts()[
                NodeType.MERCHANT_SMALL
            ],
            "number_of_medium_merchants_in_simulation": self.merchant_counts()[
                NodeType.MERCHANT_MEDIUM
            ],
            "number_of_large_merchants_in_simulation": self.merchant_counts()[
                NodeType.MERCHANT_LARGE
            ],
            "citizens_to_intermediary_ratio": self.citizens_to_intermediary_ratio,
            "intermediary_to_CB_ratio": self.intermediary_to_CB_ratio,
            "citizens_to_CB_ratio": self.citizens_to_CB_ratio,
            "merchants_to_retail_users_ratio": self.merchants_to_retail_users_ratio,
            "number_of_banked_retail_users_in_simulation": self.count_by_nation_name(
                self.number_of_banked_retail_users_in_simulation,
            ),
            "number_of_unbanked_retail_users_in_simulation": self.count_by_nation_name(
                self.number_of_unbanked_retail_users_in_simulation,
            ),
            "fraction_of_unbanked_retail_users": self.fraction_of_unbanked_retail_users,
            "p_small_merchants": self.p_small_merchants,
            "p_medium_merchants": self.p_medium_merchants,
            "p_large_merchants": self.p_large_merchants,
            "unique_cb": self.unique_cb,
            "nations": self.nations,
        }

    @property
    def number_of_small_merchants(self) -> int:
        """Get the number of small merchants."""
        return max(
            self.number_of_merchants_in_simulation
            - self.number_of_medium_merchants
            - self.number_of_large_merchants,
            0,
        )

    @property
    def number_of_medium_merchants(self) -> int:
        """Get the number of small merchants."""
        return int(
            round(self.number_of_merchants_in_simulation * self.p_medium_merchants),
        )

    @property
    def number_of_large_merchants(self) -> int:
        """Get the number of small merchants."""
        return int(
            round(self.number_of_merchants_in_simulation * self.p_large_merchants),
        )

    def cb_count_by_nation_name(self) -> dict:
        """Get a dictionary mapping nation names to the CB count."""
        return {
            nation_id: 0 if self.unique_cb else 1 for nation_id in self.nations.nations
        }

    def count_by_nation_name(self, total_n: int) -> dict[str, int]:
        """Get a dictionary mapping nation names to the total count scaled by the relative size.

        We take extra care in rounding the counts so that the total number of nodes is exactly the
         number of nodes in the simulation.
        """
        result = {}
        # sort the nations by relative size, from largest to smallest, and by nation to break ties
        nation_list = sorted(
            self.nations.nations,
            key=lambda x: (self.nations.get_spec(x).relative_size, x),
            reverse=True,
        )
        for nation_id in nation_list[:-1]:
            result[nation_id] = int(
                round(self.nations.get_spec(nation_id).relative_size * total_n),
            )
        result[nation_list[-1]] = max(total_n - sum(result.values()), 0)

        return result

    def intermediary_counts_by_nation_name(self) -> dict[str, int]:
        """Get a dictionary mapping nation names to the intermediary count.

        We impose at least one intermediary for nation.
        """
        # at least one intermediary per nation
        result = {nation_id: 1 for nation_id in self.nations.nations}

        remaining_intermediaries = self.number_of_intermediaries_in_simulation - len(
            result,
        )
        remaining_counts = self.count_by_nation_name(remaining_intermediaries)

        assert result.keys() == remaining_counts.keys()
        return {key: result[key] + remaining_counts[key] for key in result}

    def merchant_counts(self) -> dict[NodeType, dict[str, int]]:
        """Get a dictionary mapping nation names to the merchant count.

        We take extra care in rounding the merchant counts so that the total number of merchants is exactly the
         number of merchants in the simulation.
        """
        result = {}
        # sort the nations by relative size, from largest to smallest, and by nation to break ties
        nation_list = sorted(
            self.nations.nations,
            key=lambda x: (self.nations.get_spec(x).relative_size, x),
            reverse=True,
        )

        # compute the number of merchants for medium and large merchants, proportionally
        for node_type in [NodeType.MERCHANT_MEDIUM, NodeType.MERCHANT_LARGE]:
            total_n = (
                self.number_of_large_merchants
                if node_type == NodeType.MERCHANT_LARGE
                else self.number_of_medium_merchants
            )
            result[node_type] = {}
            for nation_id in nation_list[:-1]:
                result[node_type][nation_id] = int(
                    round(self.nations.get_spec(nation_id).relative_size * total_n),
                )
            result[node_type][nation_list[-1]] = max(
                total_n
                - sum(
                    result[node_type].values(),
                ),
                0,
            )

        # the remaining merchants are small
        result[NodeType.MERCHANT_SMALL] = {}
        small_merchant_count = self.count_by_nation_name(self.number_of_small_merchants)
        for nation_id in nation_list:
            result[NodeType.MERCHANT_SMALL][nation_id] = small_merchant_count[nation_id]

        return result

    @classmethod
    def initialize_from_cli_args(
        cls,
        number_of_nodes_in_simulation: int | None,
        number_of_CBs_in_simulation: int | None,
        number_of_intermediaries_in_simulation: int | None,
        number_of_retail_users_in_simulation: int | None,
        number_of_merchants_in_simulation: int | None,
        citizens_to_intermediary_ratio: float | None,
        intermediary_to_CB_ratio: float | None,
        citizens_to_CB_ratio: float | None,
        merchants_to_retail_users_ratio: float | None,
        number_of_banked_retail_users_in_simulation: int | None,
        number_of_unbanked_retail_users_in_simulation: int | None,
        fraction_of_unbanked_retail_users: float | None,
        p_small_merchants: float | None,
        p_medium_merchants: float | None,
        p_large_merchants: float | None,
        unique_cb: bool,
        nations: NationSpecs,
    ) -> "RndModel":
        """Initialize the random model parameters from command line arguments using the legacy arg parser."""
        legacy_args_dict = {
            "number_of_nodes_in_simulation": number_of_nodes_in_simulation,
            "number_of_CBs_in_simulation": number_of_CBs_in_simulation,
            "number_of_intermediaries_in_simulation": number_of_intermediaries_in_simulation,
            "number_of_retail_users_in_simulation": number_of_retail_users_in_simulation,
            "number_of_merchants_in_simulation": number_of_merchants_in_simulation,
            "citizens_to_intermediary_ratio": citizens_to_intermediary_ratio,
            "intermediary_to_CB_ratio": intermediary_to_CB_ratio,
            "citizens_to_CB_ratio": citizens_to_CB_ratio,
            "merchants_to_retail_users_ratio": merchants_to_retail_users_ratio,
            "number_of_banked_retail_users_in_simulation": number_of_banked_retail_users_in_simulation,
            "number_of_unbanked_retail_users_in_simulation": number_of_unbanked_retail_users_in_simulation,
            "fraction_of_unbanked_retail_users": fraction_of_unbanked_retail_users,
            "p_small_merchants": p_small_merchants,
            "p_medium_merchants": p_medium_merchants,
            "p_large_merchants": p_large_merchants,
            "unique_cb": unique_cb,
            "nations": nations,
        }
        # remove entries with none values
        legacy_args_dict = {k: v for k, v in legacy_args_dict.items() if v is not None}
        completed_params = infer_missing_rnd_model_params(legacy_args_dict)
        return cls(**completed_params)

    def __post_init__(self) -> None:
        """Post init checks."""
        if self.nations.nb_nations > self.number_of_intermediaries_in_simulation:
            msg = "the number of intermediaries cannot be smaller than the number of nations"
            raise ValueError(msg)

        if (
            sum(
                [
                    self.p_small_merchants,
                    self.p_medium_merchants,
                    self.p_large_merchants,
                ],
            )
            != 1.0
        ):
            msg = "the probabilities of having small, medium and large merchants must sum to 1"
            raise ValueError(msg)


@dataclasses.dataclass(frozen=True)
class Args:
    """Data class to store command line arguments.

    The supported arguments are:

        version: bool, print version and exit
        verbose: bool, verbose output
        input_file: Path, input file
        output_dir: Path, output directory
        output_formatter: str, output formatter for Networkx graph
        rnd_model: RndModel, random model parameters
        seed: Optional[int], random seed
        dump_network: bool, whether to dump the main network
        dump_subnetworks: bool, whether to dump the subnetworks
        unique_cb: bool, force one CB for the entire network
        subnetwork_filter: Optional[str], subnetwork filter
        fake_demo_names: bool, whether to use fake demo names
        deploy_node_count: int, the number of nodes to deploy
    """

    version: bool
    verbose: bool
    input_file: Path
    output_dir: Path
    output_formatter: Callable
    rnd_model: RndModel
    seed: int | None = DEFAULT_RANDOM_SEED
    dump_network: bool = DEFAULT_DUMP_NETWORK
    dump_subnetworks: bool = DEFAULT_DUMP_SUBNETWORKS
    subnetwork_filter: str | None = DEFAULT_SUBNETWORK_FILTER
    fake_demo_names: bool = DEFAULT_FAKE_DEMO_NAMES
    deploy_node_count: int = DEFAULT_DEPLOY_NODE_COUNT

    def __post_init__(self) -> None:
        """Post init checks."""
        if self.deploy_node_count < 1:
            msg = "the deploy node count must be greater than 0"
            raise ValueError(msg)

    def print_args(self) -> str:
        """Get a string representation of the arguments."""
        return "\n".join(
            [""]
            + [
                indent(f"{attr}={pprint.pformat(value)},", " " * 4)
                for attr, value in sorted(dataclasses.asdict(self).items())
            ],
        )

    def legacy_args_dict(self) -> dict:
        """Get a dictionary representation of (a subset of) the arguments."""
        # TODO: remove when the legacy code is refactored
        # take the output formatter name from the function name
        file_format = self.output_formatter.__name__.split("_")[1]
        return {
            "output_dir": self.output_dir,
            "output_file": NETWORK_OUTPUT_FILENAME.with_suffix(f".{file_format}"),
            "output_formatter": self.output_formatter,
            "dump_network": self.dump_network,
            "dump_subnetworks": self.dump_subnetworks,
        }

    @property
    def dump(self) -> bool:
        """Whether to dump the network or the subnetworks."""
        return self.dump_network or self.dump_subnetworks


def get_description() -> str:
    """Get the command line description."""
    return dedent(
        """\

    Follow a few examples of how to use the command line interface.

    Example 1: Generate a network with 1 Central Bank, 2 intermediaries, 3 retail users and 4 merchants

        $ python plasma_network_generator/commands/networkx_generator.py --input capacities.json --nb-cb 1 --nb-intermediaries 2 --nb-retail 3 --nb-merchants 4

    Example 2: alternative syntax using the --size option:

        $ python plasma_network_generator/commands/networkx_generator.py --input capacities.json --size "1 2 3 4"

    Example 3: Customize the nations of the network (all of the same size):

        $ python plasma_network_generator/commands/networkx_generator.py --input capacities.json --size "3 10 20 30" --nations "IT, FR, DE"

    Example 4: Customize the nations of the network (with different sizes):

        $ python plasma_network_generator/commands/networkx_generator.py --input capacities.json --size "3 10 20 30" --nation-specs IT:0.5 FR:0.3 DE:0.2

    Example 5: Use Eurosystem default as nation specs:

        $ python plasma_network_generator/commands/networkx_generator.py --input capacities.json --size "20 100 200 300"

    Example 6: Use Eurosystem default, but override certain nations:

        $ python plasma_network_generator/commands/networkx_generator.py --input capacities.json --size "20 100 200 300" --nation-specs-overrides DE:0.20 IT:0.20 FR:0.20 ES:0.20

    \
    """,
    )


def get_parser() -> argparse.ArgumentParser:
    """Get the command line parser."""
    version = get_version()
    parser = argparse.ArgumentParser(
        description=f"Plasma Network Generator v{version}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=get_description(),
    )
    parser.add_argument("--version", action="store_true", help="print version and exit")
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        help=f"input file (default: '{DEFAULT_INPUT_FILE}')",
        default=DEFAULT_INPUT_FILE,
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help=f"output directory (default: '{DEFAULT_OUTPUT_DIR}')",
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--output-formatter",
        action=SupportedNetworkxFormatter,
        help=f"Networkx output formatter; one of {SupportedNetworkxFormatter.SUPPORTED_FORMATTERS} "
        f"(default: '{DEFAULT_OUTPUT_FORMATTER}')",
        default=nx.write_gml,
    )
    parser.add_argument(
        "--nb-nodes",
        type=integer_in_human_format,  # type: ignore
        help="the number of nodes in the simulation",
        default=None,
    )
    parser.add_argument(
        "--size",
        type=network_size_string,  # type: ignore
        help="the size specification of the network",
        default=None,
    )
    parser.add_argument(
        "--nb-cb",
        type=integer_in_human_format,  # type: ignore
        help="the number of CBs",
        default=None,
    )
    parser.add_argument(
        "--nb-intermediaries",
        type=integer_in_human_format,  # type: ignore
        help="the number of intermediaries",
        default=None,
    )
    parser.add_argument(
        "--nb-retail",
        type=integer_in_human_format,  # type: ignore
        help="the number of retail",
        default=None,
    )
    parser.add_argument(
        "--nb-merchants",
        type=integer_in_human_format,  # type: ignore
        help="the number of merchants",
        default=None,
    )
    parser.add_argument(
        "--citizens-to-intermediary-ratio",
        type=nonnegative_float,  # type: ignore
        help="the citizens to intermediary ratio",
        default=None,
    )
    parser.add_argument(
        "--intermediary-to-cb-ratio",
        type=nonnegative_float,  # type: ignore
        help="the citizens to intermediary ratio",
        default=None,
    )
    parser.add_argument(
        "--citizens-to-cb-ratio",
        type=nonnegative_float,  # type: ignore
        help="the citizens to CB ratio",
        default=None,
    )
    parser.add_argument(
        "--merchants-to-retail-users-ratio",
        type=nonnegative_float,  # type: ignore
        help="the merchants to retail users ratio",
        default=None,
    )
    parser.add_argument(
        "--nb-banked-retail-users",
        type=check_nonnegative_integer,  # type: ignore
        help="the number of banked retail users",
        default=None,
    )
    parser.add_argument(
        "--nb-unbanked-retail-users",
        type=check_nonnegative_integer,  # type: ignore
        help="the number of unbanked retail users",
        default=None,
    )
    parser.add_argument(
        "--fraction-of-unbanked-retail-users",
        type=float_between_0_and_1,  # type: ignore
        help="the fraction of unbanked retail users",
        default=None,
    )
    parser.add_argument(
        "--p-small-merchants",
        type=float_between_0_and_1,  # type: ignore
        help="the probability of having small merchants",
        default=None,
    )
    parser.add_argument(
        "--p-medium-merchants",
        type=float_between_0_and_1,  # type: ignore
        help="the probability of having medium merchants",
        default=None,
    )
    parser.add_argument(
        "--p-large-merchants",
        type=float_between_0_and_1,  # type: ignore
        help="the probability of having large merchants",
        default=None,
    )
    parser.add_argument(
        "-s",
        "--seed",
        type=int,
        help=f"random seed (default: {DEFAULT_RANDOM_SEED})",
        default=DEFAULT_RANDOM_SEED,
    )
    parser.add_argument(
        "--no-dump-network",
        action="store_false",
        help=f"don't dump the main network (default: {DEFAULT_DUMP_NETWORK})",
        default=DEFAULT_DUMP_NETWORK,
    )
    parser.add_argument(
        "--dump-subnetworks",
        action="store_true",
        help=f"whether to dump the subnetworks (default: {DEFAULT_DUMP_SUBNETWORKS})",
        default=DEFAULT_DUMP_SUBNETWORKS,
    )
    parser.add_argument(
        "--unique-cb",
        action="store_true",
        help=f"force one CB for the entire network (default: {DEFAULT_UNIQUE_CB})",
        default=DEFAULT_UNIQUE_CB,
    )
    parser.add_argument(
        "-f",
        "--filter",
        type=str,
        help=f"subnetwork filter (default: {DEFAULT_SUBNETWORK_FILTER})",
        default=DEFAULT_SUBNETWORK_FILTER,
    )
    parser.add_argument(
        "--fake-demo-names",
        action="store_true",
        help=f"whether to use fake demo names (default: {DEFAULT_FAKE_DEMO_NAMES})",
        default=DEFAULT_FAKE_DEMO_NAMES,
    )
    parser.add_argument(
        "--deploy_node_count",
        type=check_positive_integer,  # type: ignore
        help=f"the (default: {DEFAULT_DEPLOY_NODE_COUNT})",
        default=DEFAULT_DEPLOY_NODE_COUNT,
    )

    # add group for nation specification
    nation_group = parser.add_mutually_exclusive_group()
    nation_group.add_argument(
        "--nations",
        type=set_of_strings,  # type: ignore
        help="the nations of the generated network",
    )
    nation_group.add_argument(
        "--nation-specs",
        type=NationSpec.from_string,
        nargs="+",
        help="Add a nation to the generated network specified as follows: '<name>,<relative_size>' (e.g. "
        "--nation-specs 'IT:0.5' 'FR:0.3' 'DE:0.2')",
    )
    nation_group.add_argument(
        "--nation-specs-overrides",
        type=NationSpec.from_string,
        nargs="+",
        help="Override the default nation specifications.",
    )

    return parser


def get_size_spec_from_args(raw_args: argparse.Namespace, nb_nations: int) -> dict:
    """Get the network size specification from command line arguments."""
    if raw_args.size is not None and any(
        n is not None
        for n in [
            raw_args.nb_nodes,
            raw_args.nb_cb,
            raw_args.nb_intermediaries,
            raw_args.nb_retail,
            raw_args.nb_merchants,
        ]
    ):
        msg = "the size specification cannot be used together with the other size arguments"
        raise CliArgsValidationError(msg)

    if raw_args.size is not None:
        nb_cbs = raw_args.size[0]
        if raw_args.unique_cb and nb_cbs != 1:
            msg = "the unique CB flag cannot be used together with a size specification with more than one CB"
            raise CliArgsValidationError(msg)
        nb_intermediaries = raw_args.size[1]
        nb_retail_users = raw_args.size[2]
        nb_merchants = raw_args.size[3]
    else:
        if raw_args.unique_cb and raw_args.nb_cb is not None:
            msg = "the unique CB flag cannot be used together with the number of CBs argument"
            raise CliArgsValidationError(msg)
        nb_cbs = raw_args.nb_cb
        nb_intermediaries = raw_args.nb_intermediaries
        nb_retail_users = raw_args.nb_retail
        nb_merchants = raw_args.nb_merchants

    if nb_cbs != nb_nations and not raw_args.unique_cb:
        logging.warning(
            "each nation must have exactly one CB (if --unique-cb not provided), but got a number of CBs "
            "equal to %s; setting it to the number of nations %s",
            nb_cbs,
            nb_nations,
        )
        nb_cbs = nb_nations

    return {
        "number_of_CBs_in_simulation": nb_cbs,
        "number_of_intermediaries_in_simulation": nb_intermediaries,
        "number_of_retail_users_in_simulation": nb_retail_users,
        "number_of_merchants_in_simulation": nb_merchants,
    }


def parse_nation_spec(raw_args: argparse.Namespace) -> NationSpecs:
    """Parse the nation specification from raw arguments."""
    if raw_args.nation_specs_overrides is not None:
        overrides_by_country = {
            spec.name: spec for spec in raw_args.nation_specs_overrides
        }
        new_specs = DEFAULT_NATIONS.override(overrides_by_country)
        return new_specs
    if raw_args.nation_specs is not None:
        return NationSpecs.from_sequence(raw_args.nation_specs)
    if raw_args.nations is not None:
        return NationSpecs.from_nation_list(raw_args.nations)
    return DEFAULT_NATIONS


def parse_size_spec(raw_args: argparse.Namespace) -> RndModel:
    """Parse the size specification from raw arguments."""
    nation_spec = parse_nation_spec(raw_args)
    sizes_spec = get_size_spec_from_args(raw_args, nation_spec.nb_nations)
    rnd_model = RndModel.initialize_from_cli_args(
        number_of_nodes_in_simulation=raw_args.nb_nodes,
        **sizes_spec,
        citizens_to_intermediary_ratio=raw_args.citizens_to_intermediary_ratio,
        intermediary_to_CB_ratio=raw_args.intermediary_to_cb_ratio,
        citizens_to_CB_ratio=raw_args.citizens_to_cb_ratio,
        merchants_to_retail_users_ratio=raw_args.merchants_to_retail_users_ratio,
        number_of_banked_retail_users_in_simulation=raw_args.nb_banked_retail_users,
        number_of_unbanked_retail_users_in_simulation=raw_args.nb_unbanked_retail_users,
        fraction_of_unbanked_retail_users=raw_args.fraction_of_unbanked_retail_users,
        p_small_merchants=raw_args.p_small_merchants,
        p_medium_merchants=raw_args.p_medium_merchants,
        p_large_merchants=raw_args.p_large_merchants,
        unique_cb=raw_args.unique_cb,
        nations=nation_spec,
    )
    assert not rnd_model.unique_cb or rnd_model.number_of_CBs_in_simulation == 1, (
        "the unique CB flag is not consistent with the provided or inferred number of CBs"
    )
    return rnd_model


def parse_args() -> Args:
    """Parse command line arguments."""
    parser = get_parser()
    raw_args = parser.parse_args()

    rnd_model = parse_size_spec(raw_args)

    return Args(
        version=raw_args.version,
        verbose=raw_args.verbose,
        input_file=raw_args.input.resolve(),
        output_dir=raw_args.output_dir.resolve(),
        output_formatter=raw_args.output_formatter,
        rnd_model=rnd_model,
        seed=raw_args.seed,
        dump_network=raw_args.no_dump_network,
        dump_subnetworks=raw_args.dump_subnetworks,
        subnetwork_filter=raw_args.filter,
        fake_demo_names=raw_args.fake_demo_names,
        deploy_node_count=raw_args.deploy_node_count,
    )


def _generate_network(args: Args) -> tuple[nx.Graph, list[nx.Graph]]:
    """Do the main job."""
    logging.info("Reading input file %s", args.input_file)

    # TODO: this is a workaround to avoid changing the legacy code
    rnd_model_dict = args.rnd_model.asdict()

    logging.info("Loading capacities from input file")
    model_params = load_json(args.input_file)
    rnd_model_dict.update(model_params)

    # override the random seed if given
    # TODO: bad practice, we should use a custom random generator
    np.random.seed(args.seed)

    logging.info("Generating the main payment network")
    layer_nodes, subnetworks_models = payment_subnetworks_random_models(rnd_model_dict)

    keypath_to_value = dict(filter(lambda kv: "->" in kv[0], rnd_model_dict.items()))
    for keypath in keypath_to_value:
        inject_custom_param_value(
            subnetworks_models,
            keypath,
            keypath_to_value[keypath],
        )

    subnetworks_models = subnetworks_models.values()
    subnetworks_filter = args.subnetwork_filter
    subnetworks_models = filter(
        lambda sn: subnetworks_filter is None
        or sn["[edge]"]["type"][1] == subnetworks_filter,
        subnetworks_models,
    )
    subnetworks_models = [flatten_attribute_names(sn) for sn in subnetworks_models]

    logging.debug("Dumping network information")
    with patch("builtins.print", logging.debug):
        dump_info_about_layeers_and_nodes(layer_nodes, rnd_model_dict)
        dump_info_about_network_random_models(subnetworks_models)

    (plasma_network, subnetwork_instances) = generate_plasma_network(
        subnetworks_models,
        args.seed,
        args.rnd_model.nations,
        args.rnd_model.unique_cb,
    )
    postprocess_plasma_network(plasma_network, {})
    plasma_network.graph["name"] = "Plasma Network"
    plasma_network.graph["description"] = "A 3-layer payment network"

    if args.fake_demo_names:
        logging.info("Add fake demo names")
        plasma_network = demoize_node_names(plasma_network)
        subnetwork_instances = filter(demoize_node_names, subnetwork_instances)

    return plasma_network, subnetwork_instances


def _execute(args: Args) -> tuple[nx.Graph, list[nx.Graph]] | None:
    if args.version:
        print(get_version())
        return None

    configure_logging(args.verbose)

    # Check input file exists
    check_file_exists(args.input_file, CliArgsValidationError)

    if args.dump:
        # Validate output directory. Create it if it does not exist.
        args.output_dir.mkdir(parents=True, exist_ok=True)
        check_path_is_directory(args.output_dir, CliArgsValidationError)
        check_dir_is_empty(args.output_dir, CliArgsValidationError)

    logging.info("Plasma Network Generator v%s", get_version())
    logging.debug("Arguments: %s", args.print_args())

    plasma_network, subnetwork_instances = _generate_network(args)

    if args.verbose:
        logging.debug("Dumping network analysis")
        with patch("builtins.print", logging.debug):
            dump_network_analysis(plasma_network, subnetwork_instances)

    if args.dump:
        logging.info("Saving plasma network")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        dump_plasma_network(
            plasma_network,
            subnetwork_instances,
            args.legacy_args_dict(),
        )

    return plasma_network, subnetwork_instances


def main() -> None:
    """Execute the main script."""
    try:
        args: Args = parse_args()
        _execute(args)
        sys.exit(EXIT_SUCCESS)
    except KeyboardInterrupt:
        logging.info("\nInterrupted by user")
        sys.exit(EXIT_FAILURE)
    except CliArgsValidationError as e:
        logging.error(e)
        sys.exit(EXIT_FAILURE)
    except Exception:
        logging.exception("Unexpected error")
        sys.exit(EXIT_FAILURE)


if __name__ == "__main__":
    main()
