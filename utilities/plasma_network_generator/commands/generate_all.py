#!/usr/bin/env python3
"""Generate a set of networks."""
import argparse
import dataclasses
import logging
import pprint
import sys
from collections.abc import Sequence
from pathlib import Path
from textwrap import dedent, indent
from typing import cast

# Configure Metis environment variables
import os
os.environ["METIS_DLL"] = os.path.abspath(os.path.join(os.path.dirname(__file__),f"../../../build/usr/lib/libmetis.so"))
os.environ["METIS_REALTYPEWIDTH"] = "64"
os.environ["METIS_IDXTYPEWIDTH"] = "64"

import networkx as nx

from plasma_network_generator.cloth_dump import (
    cloth_output,
    plasma_network_generator_cloth_dumb_main,
)
from plasma_network_generator.commands.networkx_generator import (
    DEFAULT_NATIONS,
    RndModel,
)
from plasma_network_generator.commands.networkx_generator import (
    Args as NetworkxGeneratorArgs,
)
from plasma_network_generator.commands.networkx_generator import (
    _execute as execute_networkx_generator,
)
from plasma_network_generator.core import NationSpecs, select_eurosystem_subset
from plasma_network_generator.exceptions import CliArgsValidationError
from plasma_network_generator.utils import (
    EXIT_FAILURE,
    EXIT_SUCCESS,
    SeedGenerator,
    check_dir_is_empty,
    check_file_is_file,
    check_path_is_directory,
    check_positive_integer,
    configure_logging,
    float_between_0_and_1,
    fraction_format_str,
    get_version,
    nb_digits_after_comma,
    network_size_string,
    set_of_strings,
)

DEFAULT_OUTPUT_DIR = Path("output")
DEFAULT_RANDOM_SEED: int | None = 42
DEFAULT_FRACTION_OF_UNBANKED_RETAIL_USERS: float = 0.0


@dataclasses.dataclass(frozen=True)
class Args:
    """Command line arguments."""

    version: bool
    verbose: bool
    model_params_file: Path
    output_dir: Path
    nb_partitions: Sequence[int]
    nb_intermediaries: int
    nb_retail: int
    nb_merchants: int
    fraction_of_unbanked_retail_users: float
    p_small_merchants: float
    p_medium_merchants: float
    p_large_merchants: float
    capacity_fractions: Sequence[float]
    nations: NationSpecs
    seed: int | None = None

    def __post_init__(self):
        """Post initialization checks."""
        if (
            self.p_small_merchants + self.p_medium_merchants + self.p_large_merchants
        ) != 1.0:
            msg = "The sum of the probabilities of having small, medium and large merchants must be 1.0"
            raise CliArgsValidationError(msg)

    def print_args(self) -> str:
        """Get a string representation of the arguments."""
        return "\n".join(
            [""]
            + [
                indent(f"{attr}={pprint.pformat(value)},", " " * 4)
                for attr, value in sorted(dataclasses.asdict(self).items())
            ],
        )


def get_description() -> str:
    """Get the command line description."""
    return dedent(
        """\
    Script to pipeline network-generator and cloth-dump scripts.

    Example usage: Generate a network with 1 Central Bank, 2 intermediaries, 3 retail users and 4 merchants

        $ python plasma_network_generator/commands/generate-all \\
            -k 1 2 3 4 --size "20 100 200 200" \\
            --fraction-of-unbanked-retail-users 0.2 \\
            --p-small-merchants 0.4 \\
            --p-medium-merchants 0.3 \\
            --p-large-merchants 0.3 \\
            --output-dir output \\
            --model-params-file model_params.json
    """,
    )


def get_parser() -> argparse.ArgumentParser:
    """Get the command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate a set of networks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=get_description(),
    )
    parser.add_argument("--version", action="store_true", help="print version and exit")
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    parser.add_argument(
        "-k",
        "--nb-partitions",
        type=check_positive_integer,
        help="Number of partitions",
        nargs="+",
        required=True,
    )
    parser.add_argument(
        "-m",
        "--model-params-file",
        help="The model params file, including capacities (to be scaled)",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--size",
        type=network_size_string,  # type: ignore
        help="the size specification of the network (default '1,30,300k,3k')",
        default="1 30 300k 3k",
    )
    parser.add_argument(
        "--fraction-of-unbanked-retail-users",
        type=float_between_0_and_1,  # type: ignore
        help=f"the fraction of unbanked retail users (default: {DEFAULT_FRACTION_OF_UNBANKED_RETAIL_USERS})",
        default=DEFAULT_FRACTION_OF_UNBANKED_RETAIL_USERS,
    )
    parser.add_argument(
        "--p-small-merchants",
        type=float_between_0_and_1,  # type: ignore
        help="the probability of having small merchants",
        default=0.4,
    )
    parser.add_argument(
        "--p-medium-merchants",
        type=float_between_0_and_1,  # type: ignore
        help="the probability of having medium merchants",
        default=0.3,
    )
    parser.add_argument(
        "--p-large-merchants",
        type=float_between_0_and_1,  # type: ignore
        help="the probability of having large merchants",
        default=0.3,
    )
    parser.add_argument(
        "-s",
        "--seed",
        type=int,
        help=f"random seed (default: {DEFAULT_RANDOM_SEED})",
        default=DEFAULT_RANDOM_SEED,
    )
    parser.add_argument(
        "--nations",
        type=set_of_strings,  # type: ignore
        default=None,
        help="the nations of the generated network",
    )
    parser.add_argument(
        "-f",
        "--capacity-fractions",
        type=float_between_0_and_1,  # type: ignore
        default=[i / 100 for i in range(0, 101, 10)],
        help="the capacity fractions to use (default: 0.0 0.1 0.2 ... 1.0)",
        nargs="+",
    )
    return parser


def parse_args() -> Args:
    """Parse command line arguments."""
    parser = get_parser()
    raw_args = parser.parse_args()

    nb_cb, nb_intermediaries, nb_retail, nb_merchants = raw_args.size

    nations = (
        select_eurosystem_subset(raw_args.nations)
        if raw_args.nations is not None
        else DEFAULT_NATIONS
    )

    return Args(
        version=raw_args.version,
        verbose=raw_args.verbose,
        model_params_file=raw_args.model_params_file.resolve(),
        output_dir=raw_args.output_dir.resolve(),
        nb_partitions=tuple(raw_args.nb_partitions),
        nb_intermediaries=nb_intermediaries,
        nb_retail=nb_retail,
        nb_merchants=nb_merchants,
        fraction_of_unbanked_retail_users=raw_args.fraction_of_unbanked_retail_users,
        p_small_merchants=raw_args.p_small_merchants,
        p_medium_merchants=raw_args.p_medium_merchants,
        p_large_merchants=raw_args.p_large_merchants,
        capacity_fractions=raw_args.capacity_fractions,
        nations=nations,
        seed=raw_args.seed,
    )


def call_cloth_dump(input_file: Path, output_dir: Path, n_partitions: int) -> None:
    """Call the cloth dump."""
    plasma_network_generator_cloth_dumb_main(
        [
            "cloth_dump.py",
            "-input",
            str(input_file),
            "-dir",
            str(output_dir),
            "-k",
            str(n_partitions),
        ],
    )


def scale_capacities(
    plasma_network: nx.MultiDiGraph,
    capacity_percentage: float,
) -> nx.MultiDiGraph:
    """Scale the capacities of the plasma network.

    We take extra care to round the capacities to integers, and in such a way that the sum of the balances
    in the same channel is equale to the scaled capacity.
    """
    scaled_plasma_network = plasma_network.copy()
    scaled_edges = {}

    # sort the edges by u, v, as a "defensive" countermeasure to potential issues in reproducibility
    for u, v, data in sorted(
        scaled_plasma_network.edges(data=True),
        key=lambda x: (x[0], x[1]),
    ):
        # do not scale 2<>3 channel capacities
        if data["type"] in ["1<>1", "2<>3B", "2<>3Msmall", "2<>3Mmedium", "2<>3Mlarge"]:
            continue
        # scale the capacity
        scaled_capacity = round(data["capacity"] * capacity_percentage)
        data["capacity"] = scaled_capacity

        # scale the balance
        # if it is the first time we process the channel, just scale the direction u->v using the percentage
        if (u, v) not in scaled_edges:
            scaled_balance = round(data["balance"] * capacity_percentage)
            # save the balance to be used when processing the opposite direction
            scaled_edges[(u, v)] = scaled_balance
            scaled_edges[(v, u)] = scaled_capacity - scaled_balance
        else:
            # this time we process the opposite direction v->u. We retrieve the value from the dictionary
            scaled_balance = scaled_edges[(u, v)]
        data["balance"] = scaled_balance

    # TODO the pre-channel balances are not updated

    return cast(nx.MultiDiGraph, scaled_plasma_network)


def _do_job(args: Args) -> None:
    """Do the main job."""
    logging.info("Reading the input directory content %s", args.model_params_file)

    seed_gen = SeedGenerator(args.seed)

    logging.info("Reading file %s", args.model_params_file)

    logging.info(
        "Selected nation size specifications:\n%s", pprint.pformat(args.nations)
    )

    networkx_generator_output_dir = args.output_dir / "generator_output"
    rnd_model = RndModel.initialize_from_cli_args(
        number_of_nodes_in_simulation=None,
        number_of_CBs_in_simulation=1,
        number_of_intermediaries_in_simulation=args.nb_intermediaries,
        number_of_retail_users_in_simulation=args.nb_retail,
        number_of_merchants_in_simulation=args.nb_merchants,
        citizens_to_intermediary_ratio=None,
        intermediary_to_CB_ratio=None,
        citizens_to_CB_ratio=None,
        merchants_to_retail_users_ratio=None,
        number_of_banked_retail_users_in_simulation=None,
        number_of_unbanked_retail_users_in_simulation=None,
        fraction_of_unbanked_retail_users=args.fraction_of_unbanked_retail_users,
        p_small_merchants=args.p_small_merchants,
        p_medium_merchants=args.p_medium_merchants,
        p_large_merchants=args.p_large_merchants,
        unique_cb=False,
        nations=args.nations,
    )
    logging.info(
        "********** calling networkx generator using model params file %s **********",
        args.model_params_file,
    )
    networkx_generator_args = NetworkxGeneratorArgs(
        version=False,
        verbose=args.verbose,
        input_file=args.model_params_file,
        output_dir=networkx_generator_output_dir,
        output_formatter=nx.write_graphml,
        rnd_model=rnd_model,
        seed=args.seed,
        dump_network=False,
        dump_subnetworks=False,
    )
    plasma_network, _ = execute_networkx_generator(networkx_generator_args)

    max_nb_digits = max(map(nb_digits_after_comma, args.capacity_fractions))
    for cap_fraction in args.capacity_fractions:
        scaled_plasma_network = scale_capacities(
            plasma_network,
            cap_fraction,
        )
        capacity_output_dir = args.output_dir / (
            "capacity-" + fraction_format_str(cap_fraction, max_nb_digits)
        )
        for n_partitions in args.nb_partitions:
            logging.info(
                "### Calling cloth dump with number of partitions %d ###",
                n_partitions,
            )
            cloth_dump_output_dir = capacity_output_dir / f"k_{n_partitions:02d}"
            cloth_dump_output_dir.mkdir(parents=True, exist_ok=True)
            cloth_output(
                scaled_plasma_network,
                cloth_dump_output_dir,
                n_partitions,
            )

    logging.info("*" * 30)
    logging.info("Done!")


def _execute(args: Args) -> None:
    if args.version:
        print(get_version())
        return

    configure_logging(args.verbose)

    # Check input dir exists and that is not empty
    check_file_is_file(args.model_params_file, CliArgsValidationError)

    # Validate output directory. Create it if it does not exist.
    args.output_dir.mkdir(parents=True, exist_ok=True)
    check_path_is_directory(args.output_dir, CliArgsValidationError)
    check_dir_is_empty(args.output_dir, CliArgsValidationError)

    logging.info("Plasma Network Generator v%s", get_version())
    logging.debug("Arguments: %s", args.print_args())
    _do_job(args)


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
