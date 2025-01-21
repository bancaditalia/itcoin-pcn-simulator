########################################################################################################################
#                         Copyright (c) 2019-2021 Banca d'Italia - All Rights Reserved                                 #
#                                                                                                                      #
# This file is part of the "itCoin" project.                                                                           #
# Unauthorized copying of this file, via any medium, is strictly prohibited.                                           #
# The content of this and related source files is proprietary and confidential.                                        #
#                                                                                                                      #
# Written by ART (Applied Research Team) - email: appliedresearchteam@bancaditalia.it - web: https://www.bankit.art    #
########################################################################################################################

"""The generator script."""

import argparse
import dataclasses
import json
import logging
import pprint
import sys
from cmath import nan
from pathlib import Path
from textwrap import dedent, indent

import numpy as np
import pandas as pd

from statistics_analyzer.core import (
    N_BATCHES,
    DistributionInnerStats,
    DistributionStats,
    GeneralStat,
    PaymentsStats,
    StatsPerMinute,
    StatType,
)
from statistics_analyzer.exceptions import CliArgsValidationError
from statistics_analyzer.utils import (
    EXIT_FAILURE,
    EXIT_SUCCESS,
    check_path_is_directory,
    configure_logging,
    count_file_in_dir,
)

DEFAULT_INPUT_DIR = Path("output_dir")
DEFAULT_OUTPUT_DIR = Path("output_dir")
PAYMENTS_OUTPUT_FILE_PATTERN = "payments_output_*.csv"
CHANNEL_OUTPUT_FILE_PATTERN = "channels_output_*.csv"


@dataclasses.dataclass(frozen=True)
class Args:
    """Data class to store command line arguments.

    The supported arguments are:

        verbose: bool, verbose output
        input_dir: Path, input directory
        rank_index: int, index of the rank to be analyzed
        output_dir: Path, output directory
    """

    verbose: bool
    input_dir: Path
    output_dir: Path
    rank_idx: int

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
        return {
            "input_dir": self.input_dir,
            "output_dir": self.output_dir,
            "rank_idx": self.rank_idx,
        }


def get_description() -> str:
    """Get the command line description."""
    return dedent(
        """\

    Follow a few examples of how to use the command line interface.

    Example 1: Generate the payment statistics for the simulation of all the ranks

        $ python cloth/cloth-statistics-analyzer/statistics_analyzer/commands/analyzer.py --input-dir ./output_dir --output-dir ./output_dir

    Example 2: Generate the payment statistics for the simulation of a specific rank

        $ python cloth/cloth-statistics-analyzer/statistics_analyzer/commands/analyzer.py --input-dir ./output_dir --output-dir ./output_dir --rank-idx 0
    \
    """,
    )


def get_parser() -> argparse.ArgumentParser:
    """Get the command line parser."""
    parser = argparse.ArgumentParser(
        description="CLoTH Statistics Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=get_description(),
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    parser.add_argument(
        "-i",
        "--input-dir",
        type=Path,
        help=f"input directory (default: '{DEFAULT_INPUT_DIR}')",
        default=DEFAULT_INPUT_DIR,
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help=f"output directory (default: '{DEFAULT_OUTPUT_DIR}')",
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--rank-idx",
        type=int,
        help="the rank index to be analyzed",
        default=None,
    )
    return parser


def parse_args() -> Args:
    """Parse command line arguments."""
    parser = get_parser()
    raw_args = parser.parse_args()

    return Args(
        verbose=raw_args.verbose,
        input_dir=raw_args.input_dir.resolve(),
        output_dir=raw_args.output_dir.resolve(),
        rank_idx=raw_args.rank_idx,
    )


def _read_channels_output_files(args: Args, pattern: str) -> pd.DataFrame:
    """Read the payments_output_*.csv files"""
    logging.debug("Reading input directory %s", args.input_dir)
    channel_output_files = sorted(args.input_dir.glob(pattern))
    if args.verbose:
        logging.debug(
            "Reading files:\n%s", "\n".join(file.name for file in channel_output_files)
        )
    all_channels_df = pd.concat(
        (pd.read_csv(f) for f in channel_output_files), ignore_index=True
    ).sort_values(by=["id"])
    return all_channels_df


def _read_payments_output_files(args: Args, pattern: str) -> pd.DataFrame:
    """Read the payments_output_*.csv files"""
    logging.debug("Reading input directory %s", args.input_dir)
    payments_output_files = sorted(args.input_dir.glob(pattern))
    if args.verbose:
        logging.debug(
            "Reading files:\n%s", "\n".join(file.name for file in payments_output_files)
        )
    all_payments_df = pd.concat(
        (
            pd.read_csv(
                f,
                dtype={
                    "id": "int64",
                    "type": "category",
                    "sender_id": "string",
                    "receiver_id": "string",
                    "amount": "int64",
                    "start_time": "int64",
                    "end_time": "int64",
                    "mpp": "category",
                    "is_success": "category",
                    "no_balance_count": "int64",
                    "offline_node_count": "int64",
                    "timeout_exp": "category",
                    "attempts": "int64",
                    "first_no_balance_error": "string",
                    "route": "string",
                    "route_ids": "string",
                },
            )
            for f in payments_output_files
        ),
        ignore_index=True,
    ).sort_values(by=["start_time"])
    return all_payments_df


def _compute_stats_per_minute(
    payments_stats: PaymentsStats, all_payments_df: pd.DataFrame
) -> None:
    df = all_payments_df.copy()
    milliseconds_in_a_minute = 60 * 1000
    df["start_minute"] = (df["start_time"] // milliseconds_in_a_minute) % (60 * 24)
    df["start_minute"] = df["start_minute"].astype("category")
    df["is_success"] = df["is_success"].astype("int")
    payments_stats.stats_per_minute[StatsPerMinute.TX_PER_MINUTE] = {
        int(hour): float(value)
        for hour, value in df[df["type"] == "0"]
        .groupby(["start_minute"], observed=False)["id"]
        .count()
        .items()
    }
    payments_stats.stats_per_minute[StatsPerMinute.PSR_PER_MINUTE] = {
        int(hour): float(value)
        for hour, value in df[df["type"] == "0"]
        .groupby(["start_minute"], observed=False)["is_success"]
        .mean()
        .round(2)
        .items()
    }
    payments_stats.stats_per_minute[StatsPerMinute.DEPOSITS_PER_MINUTE] = {
        int(hour): float(value)
        for hour, value in df[df["type"] == "1"]
        .groupby(["start_minute"], observed=False)["id"]
        .count()
        .items()
    }
    payments_stats.stats_per_minute[StatsPerMinute.WITHDRAWALS_PER_MINUTE] = {
        int(hour): float(value)
        for hour, value in df[df["type"] == "2"]
        .groupby(["start_minute"], observed=False)["id"]
        .count()
        .items()
    }
    payments_stats.stats_per_minute[StatsPerMinute.SUBMARINE_SWAPS_PER_MINUTE] = {
        int(hour): float(value)
        for hour, value in df[df["type"] == "3"]
        .groupby(["start_minute"], observed=False)["id"]
        .count()
        .items()
    }


def _compute_per_batch_stats(
    payments_stats: PaymentsStats, txs_df: pd.DataFrame
) -> None:
    total_per_batch = np.array(
        txs_df.groupby(["batch"], observed=False)["batch"].count()
    )
    payments_stats.batches[StatType.SUCCESS] = np.array(
        txs_df[txs_df["is_success"] == "1"]
        .groupby(["batch"], observed=False)["batch"]
        .count()
    )

    payments_stats.batches[StatType.ATTEMPTS] = np.array(
        txs_df[txs_df["is_success"] == "1"]
        .groupby(["batch"], observed=False)["attempts"]
        .sum()
    )
    payments_stats.batches[StatType.ATTEMPTS] = np.divide(
        payments_stats.batches[StatType.ATTEMPTS],
        payments_stats.batches[StatType.SUCCESS],
    )

    payments_stats.batches[StatType.TIME] = np.array(
        txs_df[txs_df["is_success"] == "1"]
        .groupby(["batch"], observed=False)["time"]
        .sum()
    )
    payments_stats.batches[StatType.TIME] = np.divide(
        payments_stats.batches[StatType.TIME], payments_stats.batches[StatType.SUCCESS]
    )

    payments_stats.batches[StatType.ROUTE_LENGTH] = np.array(
        txs_df[txs_df["is_success"] == "1"]
        .groupby(["batch"], observed=False)["route_length"]
        .sum()
    )
    payments_stats.batches[StatType.ROUTE_LENGTH] = np.divide(
        payments_stats.batches[StatType.ROUTE_LENGTH],
        payments_stats.batches[StatType.SUCCESS],
    )

    payments_stats.batches[StatType.FAIL_TIMEOUT_EXPIRED] = np.array(
        txs_df[(txs_df["is_success"] == "0") & (txs_df["timeout_exp"] == "1")]
        .groupby(["batch"], observed=False)["batch"]
        .count()
    )
    payments_stats.batches[StatType.FAIL_TIMEOUT_EXPIRED] = np.divide(
        payments_stats.batches[StatType.FAIL_TIMEOUT_EXPIRED], total_per_batch
    )

    payments_stats.batches[StatType.FAIL_NO_PATH] = np.array(
        txs_df[
            (txs_df["is_success"] == "0")
            & (txs_df["timeout_exp"] == "0")
            & (txs_df["route"] == -1)
        ]
        .groupby(["batch"], observed=False)["batch"]
        .count()
    )
    payments_stats.batches[StatType.FAIL_NO_PATH] = np.divide(
        payments_stats.batches[StatType.FAIL_NO_PATH], total_per_batch
    )

    payments_stats.batches[StatType.FAIL_OFFLINE] = np.array(
        txs_df[
            (txs_df["is_success"] == "0")
            & (txs_df["timeout_exp"] == "0")
            & (txs_df["route"] != -1)
            & (txs_df["offline_node_count"] > txs_df["no_balance_count"])
        ]
        .groupby(["batch"], observed=False)["batch"]
        .count()
    )
    payments_stats.batches[StatType.FAIL_OFFLINE] = np.divide(
        payments_stats.batches[StatType.FAIL_OFFLINE], total_per_batch
    )

    payments_stats.batches[StatType.FAIL_NO_BALANCE] = np.array(
        txs_df[
            (txs_df["is_success"] == "0")
            & (txs_df["timeout_exp"] == "0")
            & (txs_df["route"] != -1)
            & (txs_df["offline_node_count"] <= txs_df["no_balance_count"])
        ]
        .groupby(["batch"], observed=False)["batch"]
        .count()
    )
    payments_stats.batches[StatType.FAIL_NO_BALANCE] = np.divide(
        payments_stats.batches[StatType.FAIL_NO_BALANCE], total_per_batch
    )

    payments_stats.batches[StatType.SUCCESS] = np.divide(
        payments_stats.batches[StatType.SUCCESS], total_per_batch
    )


def _compute_distribution_stats(
    payments_stats: PaymentsStats, txs_df: pd.DataFrame
) -> None:
    # Initialize the dictionary to store the results
    result_dict = {}
    for length in txs_df["route_length"].dropna().unique():
        # Filter the DataFrame for the current route_length
        subset_df = txs_df[txs_df["route_length"] == length]

        # Count total rows for the current route_length
        total_count = len(subset_df)

        # Count rows for 'L1' and 'L2'
        l1_count = len(subset_df[subset_df["routed_by"] == "L1"])
        l2_count = len(subset_df[subset_df["routed_by"] == "L2"])

        # Store the counts in the result dictionary
        result_dict[int(length)] = {
            DistributionInnerStats.TOTAL: total_count,
            DistributionInnerStats.ROUTED_BY_L1: l1_count,
            DistributionInnerStats.ROUTED_BY_L2: l2_count,
        }

    payments_stats.distributions_stats[DistributionStats.ROUTE_LENGTH_DISTR] = (
        result_dict
    )


def _set_channel_type(x):
    if x["node1"].startswith("CB") and x["node2"].startswith("CB"):
        return "1<>1"
    if x["node1"].startswith("CB") and x["node2"].startswith("Intermediary"):
        return "1<>2"
    if x["node1"].startswith("Intermediary") and x["node2"].startswith("Intermediary"):
        return "2<>2"
    return "2<>3"


def _compute_routed_by(x):
    if x["is_success"] == "1":
        if "CB" in x["route"]:
            return "L1"
        return "L2"
    return nan


def _compute_total_capacity(args: Args) -> float:
    pattern = (
        CHANNEL_OUTPUT_FILE_PATTERN
        if args.rank_idx is None
        else f"channels_output_{args.rank_idx}.csv"
    )
    all_channels_df = _read_channels_output_files(args, pattern)
    all_channels_df["type"] = all_channels_df.apply(_set_channel_type, axis=1)
    return float(
        all_channels_df[
            (all_channels_df["type"] == "1<>2") | (all_channels_df["type"] == "2<>2")
        ]["capacity"].sum()
    )


def _do_job(args: Args, pattern: str) -> None:
    """Read the payments_output_*.csv files"""
    all_payments_df = _read_payments_output_files(args, pattern)

    """Filter transactions only (no withdrawals, deposits, and atomics swaps)"""
    txs_df = all_payments_df[all_payments_df["type"] == "0"].copy()

    """Find batch length"""
    last_payment_time = txs_df.iloc[-1]["start_time"]
    batch_length = (last_payment_time + 1) / N_BATCHES
    if args.verbose:
        logging.info("Batch length: %.2f ms", batch_length)
        logging.info("Total simulated time: %d ms", last_payment_time)

    """Add support columns"""
    txs_df["time"] = txs_df["end_time"] - txs_df["start_time"]
    txs_df["route_length"] = txs_df.apply(
        lambda x: len(x["route_ids"].split("-")) if x["is_success"] == "1" else nan,
        axis=1,
    )
    txs_df["routed_by"] = txs_df.apply(_compute_routed_by, axis=1)
    txs_df["batch"] = (
        (txs_df["start_time"] / batch_length).astype("int").astype("category")
    )

    """Compute per batch payment stats"""
    payments_stats = PaymentsStats()
    _compute_per_batch_stats(payments_stats, txs_df)
    _compute_stats_per_minute(payments_stats, all_payments_df)

    """Compute batch means"""
    payments_stats.compute_batch_means()
    if args.verbose:
        logging.info(
            "Payments batch statistics:\n%s", json.dumps(payments_stats.data, indent=4)
        )

    """Compute general stats"""
    payments_stats.general_stats[GeneralStat.TOTAL_PAYMENTS] = len(txs_df)
    payments_stats.general_stats[GeneralStat.TOTAL_DEPOSITS] = len(
        all_payments_df[all_payments_df["type"] == "1"]
    )
    payments_stats.general_stats[GeneralStat.TOTAL_WITHDRAWALS] = len(
        all_payments_df[all_payments_df["type"] == "2"]
    )
    payments_stats.general_stats[GeneralStat.TOTAL_SUBMARINE_SWAPS] = len(
        all_payments_df[all_payments_df["type"] == "3"]
    )
    payments_stats.general_stats[GeneralStat.TOTAL_SUBMARINE_SWAPS_1_1] = len(
        all_payments_df[
            (all_payments_df["type"] == "3")
            & (all_payments_df["sender_id"].str.startswith("CB"))
            & (all_payments_df["receiver_id"].str.startswith("CB"))
        ]
    )
    payments_stats.general_stats[GeneralStat.TOTAL_SUBMARINE_SWAPS_2_2] = len(
        all_payments_df[
            (all_payments_df["type"] == "3")
            & (all_payments_df["sender_id"].str.startswith("Intermediary"))
            & (all_payments_df["receiver_id"].str.startswith("Intermediary"))
        ]
    )
    payments_stats.general_stats[GeneralStat.TOTAL_SUBMARINE_SWAPS_1_2] = len(
        all_payments_df[
            (all_payments_df["type"] == "3")
            & (
                (
                    (all_payments_df["sender_id"].str.startswith("CB"))
                    & (all_payments_df["receiver_id"].str.startswith("Intermediary"))
                )
                | (
                    (all_payments_df["sender_id"].str.startswith("Intermediary"))
                    & (all_payments_df["receiver_id"].str.startswith("CB"))
                )
            )
        ]
    )
    payments_stats.general_stats[GeneralStat.TOTAL_WHOLESALE_CAPACITY] = (
        _compute_total_capacity(args)
    )
    payments_stats.general_stats[GeneralStat.TOTAL_SUCCESS_VOLUME] = float(
        txs_df[txs_df["is_success"] == "1"]["amount"].sum()
    )
    payments_stats.general_stats[GeneralStat.VOLUME_CAPACITY_RATIO] = (
        payments_stats.general_stats[GeneralStat.TOTAL_SUCCESS_VOLUME]
        / payments_stats.general_stats[GeneralStat.TOTAL_WHOLESALE_CAPACITY]
        if payments_stats.general_stats[GeneralStat.TOTAL_WHOLESALE_CAPACITY] > 0
        else nan
    )
    if args.verbose:
        logging.info(
            "Total number of payments: %d",
            payments_stats.general_stats[GeneralStat.TOTAL_PAYMENTS],
        )
        logging.info(
            "Total number of deposits: %d",
            payments_stats.general_stats[GeneralStat.TOTAL_DEPOSITS],
        )
        logging.info(
            "Total number of withdrawals: %d",
            payments_stats.general_stats[GeneralStat.TOTAL_WITHDRAWALS],
        )
        logging.info(
            "Total number of submarine swaps: %d",
            payments_stats.general_stats[GeneralStat.TOTAL_SUBMARINE_SWAPS],
        )
        logging.info(
            "Total wholesale capacity: %f EUR",
            payments_stats.general_stats[GeneralStat.TOTAL_WHOLESALE_CAPACITY],
        )
        logging.info(
            "Total success volume: %f EUR",
            payments_stats.general_stats[GeneralStat.TOTAL_SUCCESS_VOLUME],
        )
        logging.info(
            "Volume capacity ratio: %f",
            payments_stats.general_stats[GeneralStat.VOLUME_CAPACITY_RATIO],
        )

    _compute_distribution_stats(payments_stats, txs_df)

    """Write json output"""
    output_filename = (
        "cloth_output.json"
        if args.rank_idx is None
        else f"cloth_output_{args.rank_idx}.json"
    )
    output_file = args.output_dir / output_filename
    output_data = (
        payments_stats.data
        | payments_stats.general_stats
        | payments_stats.distributions_stats
        | payments_stats.stats_per_minute
    )
    output_file.write_text(json.dumps(output_data, indent=4))
    logging.info("Results written in %s", output_file)


def _execute(args: Args) -> None:
    configure_logging(args.verbose)

    # Validate input directory
    check_path_is_directory(args.input_dir, CliArgsValidationError)
    # Check files payments_output_<rank_idx>.csv exists
    pattern = (
        PAYMENTS_OUTPUT_FILE_PATTERN
        if args.rank_idx is None
        else f"payments_output_{args.rank_idx}.csv"
    )
    n = count_file_in_dir(args.input_dir, pattern, CliArgsValidationError)

    # Validate output directory. Create it if it does not exist.
    args.output_dir.mkdir(parents=True, exist_ok=True)
    check_path_is_directory(args.output_dir, CliArgsValidationError)

    logging.info("CLoTH Statistics Analyzer running at %s", args.input_dir)
    if args.verbose:
        logging.debug("Arguments: %s", args.print_args())
        logging.debug("Analyzing files from %d ranks", n)
    _do_job(args, pattern)


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
