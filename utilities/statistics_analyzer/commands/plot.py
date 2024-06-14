########################################################################################################################
#                         Copyright (c) 2019-2021 Banca d'Italia - All Rights Reserved                                 #
#                                                                                                                      #
# This file is part of the "itCoin" project.                                                                           #
# Unauthorized copying of this file, via any medium, is strictly prohibited.                                           #
# The content of this and related source files is proprietary and confidential.                                        #
#                                                                                                                      #
# Written by ART (Applied Research Team) - email: appliedresearchteam@bancaditalia.it - web: https://www.bankit.art    #
########################################################################################################################
import argparse
import dataclasses
import json
import logging
import pprint
import sys
from pathlib import Path
from textwrap import dedent, indent
from typing import Any

import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt

from statistics_analyzer.core import DistributionInnerStats
from statistics_analyzer.exceptions import CliArgsValidationError
from statistics_analyzer.utils import (
    EXIT_FAILURE,
    EXIT_SUCCESS,
    check_path_is_directory,
    configure_logging,
)


@dataclasses.dataclass(frozen=True)
class Args:
    """Data class to store command line arguments.

    The supported arguments are:

        input_dir: Path, input directory
        output_dir: Path, output directory
    """

    input_dir: Path
    output_dir: Path

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

    The following example shows how to use the command line interface.

    Example: Generate the payment statistics for the simulation of all the ranks

        $ python cloth/cloth-statistics-analyzer/statistics_analyzer/commands/plot.py --input-dir ./simulation-results --output-dir ./simulation-plots

    \
    """,
    )


def get_parser() -> argparse.ArgumentParser:
    """Get the command line parser."""
    parser = argparse.ArgumentParser(
        description="CLoTH Statistics Plotter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=get_description(),
    )
    parser.add_argument(
        "-i",
        "--input-dir",
        type=Path,
        help="input directory containing subfolders capacities-050/k_4/...",
        required=True,
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="output directory to store plots",
        required=True,
    )
    return parser


def parse_args() -> Args:
    """Parse command line arguments."""
    parser = get_parser()
    raw_args = parser.parse_args()

    return Args(
        input_dir=raw_args.input_dir.resolve(),
        output_dir=raw_args.output_dir.resolve(),
    )


def read_info(file_path: Path) -> dict[str, Any]:
    properties = {}
    # Read 'info.txt' and extract relevant information
    with file_path.open(mode="r") as file:
        for line in file:
            key, value = line.strip().split("=")
            properties[key.strip()] = value.strip()

    return properties


def read_cloth_output(file_path: Path) -> dict[str, Any]:
    # Read 'cloth_output.json' and extract relevant information
    with file_path.open(mode="r") as f:
        data = json.load(f)

    return data


def process_directory(directory_path: Path) -> dict[str, Any]:
    # Extract perc_capacity from the directory path
    perc_capacity = float(directory_path.parent.name.split("-")[1]) * 100
    # Extract seed
    seed = float(directory_path.parent.parent.name.split("_")[1])
    # Read 'info.txt'
    info_path = directory_path.parent.parent.parent / "info.txt"
    info = read_info(info_path)
    # Read 'cloth_output.json'
    cloth_output_path = directory_path / "cloth_output.json"
    cloth_output = read_cloth_output(cloth_output_path)
    # Create a dictionary with the extracted information
    waterfall = int(info["waterfall"])
    rev_waterfall = int(info["reverse_waterfall"])
    submarine_swaps = int(info["submarine_swaps"])
    if waterfall & rev_waterfall & submarine_swaps:
        rebal_mode = "rev-waterfall and swaps"
    elif waterfall & rev_waterfall:
        rebal_mode = "rev-waterfall"
    else:
        rebal_mode = "none"
    cost_wholesale_liquidity = (
        0.0001271488302 * float(cloth_output["TotalWholeSaleCapacity"]) / 100
    )
    cost_submarine_swaps = (
        0.10
        * 2
        * (
            float(cloth_output["TotalSubmarineSwaps1<>2"])
            + float(cloth_output["TotalSubmarineSwaps2<>2"])
        )
    )
    data_dict = {
        "seed": seed,
        "nb_nodes": int(info["nodes"]),
        "perc_capacity": perc_capacity,
        "tps": info["tps"],
        "waterfall": waterfall,
        "reverse_waterfall": rev_waterfall,
        "submarine_swaps": submarine_swaps,
        "rebal_mode": rebal_mode,
        "success": float(str(cloth_output["Success"]["Mean"])[:6]),
        "fail_no_path": cloth_output["FailNoPath"]["Mean"],
        "fail_no_balance": cloth_output["FailNoBalance"]["Mean"],
        "fail_offline_node": cloth_output["FailOfflineNode"]["Mean"],
        "fail_timeout_expired": cloth_output["FailTimeoutExpired"]["Mean"],
        "time": cloth_output["Time"]["Mean"],
        "attempts": cloth_output["Attempts"]["Mean"],
        "route_length": cloth_output["RouteLength"]["Mean"],
        "wholesale_capacity": float(cloth_output["TotalWholeSaleCapacity"]) / 100,
        "total_success_volume": cloth_output["TotalSuccessVolume"],
        "volume_capacity_ratio": cloth_output["VolumeCapacityRatio"],
        "total_payments": cloth_output["TotalPayments"],
        "total_deposits": cloth_output["TotalDeposits"],
        "total_withdrawals": cloth_output["TotalWithdrawals"],
        "route_length_distr": cloth_output["RouteLengthDistr"],
        "transactions_per_minute": cloth_output["TransactionsPerMinute"],
        "success_per_minute": cloth_output["SuccessPerMinute"],
        "deposits_per_minute": cloth_output["DepositsPerMinute"],
        "withdrawals_per_minute": cloth_output["WithdrawalsPerMinute"],
        "submarine_swaps_per_minute": cloth_output["SubmarineSwapsPerMinute"],
        "cost_submarine_swaps": cost_submarine_swaps,
        "cost_wholesale_liquidity": cost_wholesale_liquidity,
        "total_cost": cost_wholesale_liquidity + cost_submarine_swaps,
    }

    return data_dict


# Define the custom scale function
def forward(x):
    return np.exp(x**2)


def inverse(x):
    # Apply the inverse of the transformation
    return np.log(x**2)


def plot1(args: Args, df: pd.DataFrame) -> None:
    # PLOT 1. - total_capacity VS success
    fig, ax = plt.subplots()
    fig.set_size_inches(8, 6)
    custom_palette = {
        "rev-waterfall and swaps": "tab:green",
        "rev-waterfall": "tab:blue",
        "none": "tab:orange",
    }
    sns.lineplot(
        data=df,
        x="wholesale_capacity",
        y="success",
        hue="rebal_mode",
        marker="o",
        estimator="mean",
        palette=custom_palette,
        errorbar="sd",
        alpha=1,
    )

    ax.set_ylabel(r"\textbf{Payment Success Rate (\%)}")
    ax.set_ylim(0, 1.02)
    ax.set_yscale("function", functions=(forward, inverse))
    y_minor_ticks = [0.1, 0.5, 0.8, 0.9, 0.95, 1]
    ax.yaxis.set_major_locator(ticker.FixedLocator(y_minor_ticks))
    ax.yaxis.set_major_formatter(
        ticker.PercentFormatter(xmax=1, decimals=0, is_latex=True)
    )
    ax.yaxis.set_minor_formatter(
        ticker.PercentFormatter(
            xmax=1,
            decimals=0,
        )
    )

    ax.set_xlabel(r"\textbf{Per Channel Liquidity}")
    ax.set_xscale("symlog", linthresh=50000)
    ax.set_xlim(0, 1e9)
    major_ticks = [6e3, 60e3, 600e3, 6e6, 60e6, 600e6]
    custom_labels = [
        "6k\n\n\n100\n50",
        "60k\n\n\n1k\n500",
        "600k\n\n\n10k\n5k",
        "6M\n\n\n100k\n50k",
        "60M\n\n\n1M\n500k",
        "600M\n\n\n10M\n5M",
    ]
    ax.xaxis.set_major_locator(ticker.FixedLocator(major_ticks))
    ax.xaxis.set_major_formatter(ticker.FixedFormatter(custom_labels))
    ax.tick_params(labelsize=20)
    # Add annotation to the bottom center
    plt.text(
        0.25,
        -0.18,
        r"\textbf{Total Network Liquidity}",
        transform=plt.gca().transAxes,
        fontsize=20,
        color="black",
        alpha=0.9,
    )

    # Add annotation to the left-bottom corner
    # plt.text(-0.34, -0.42, 'Tier 1 - Tier 2:\nWithin Tier 2:', transform=plt.gca().transAxes,
    # fontsize=20, color='gray', bbox=dict(facecolor='white', alpha=0.8))
    ax.annotate(
        "Tier 1 - Tier 2:\nWithin Tier 2:",
        (0, 0),
        xytext=(-70, -70),
        textcoords="offset points",
        ha="center",
        va="top",
        rotation=0,
        color="gray",
    )

    # Create the legend with custom labels
    handles, labels = plt.gca().get_legend_handles_labels()
    labels = [
        "Full",
        "None",
        "(Rev) Waterfall only",
    ]
    order = [0, 2, 1]
    ax.legend(
        title="Rebalancing mode",
        handles=[handles[idx] for idx in order],
        labels=[labels[idx] for idx in order],
        loc="lower right",
    )
    plt.tight_layout()
    fig.savefig(
        f"{args.output_dir}/capacity_vs_successrate.pdf",
        format="pdf",
        pad_inches=0,
        bbox_inches="tight",
    )
    plt.close(fig)


def plot3(args: Args, df: pd.DataFrame) -> None:
    fig, (ax1, ax2) = plt.subplots(2, 1, layout="constrained")
    fig.set_size_inches(10.5, 8)
    df = df[
        (df["perc_capacity"] == 0.2)
        | (df["perc_capacity"] == 0.1)
        | (df["perc_capacity"] == 1.0)
    ]
    blues = sns.color_palette("ch:s=.25,rot=-.25")

    # Generate the submarine_swaps_per_minute DataFrame
    window_size = 15
    submarine_swaps_per_minute = pd.DataFrame(
        [
            {
                "minute": int(minute),
                "number": number,
                "perc_capacity": row["perc_capacity"],
                "seed": row["seed"],
            }
            for _, row in df.iterrows()
            for minute, number in row["submarine_swaps_per_minute"].items()
        ]
    ).sort_values(by=["perc_capacity", "seed", "minute"])
    submarine_swaps_per_minute["tx_smooth"] = (
        submarine_swaps_per_minute.groupby(["perc_capacity", "seed"])["number"]
        .rolling(window=window_size, min_periods=1)
        .mean()
        .reset_index(level=[0, 1], drop=True)
    )

    # Generate the deposits_per_minute DataFrame
    deposits_per_minute_c_01 = pd.DataFrame(
        [
            {
                "minute": int(minute),
                "number": number,
                "perc_capacity": row["perc_capacity"],
                "seed": row["seed"],
            }
            for _, row in df[df["perc_capacity"] == 0.1].iterrows()
            for minute, number in row["deposits_per_minute"].items()
        ]
    ).sort_values(by=["minute", "seed"])

    deposits_per_minute_c_01["tx_smooth"] = (
        deposits_per_minute_c_01.groupby("seed")["number"]
        .rolling(window=window_size, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )

    # Generate the withdrawals_per_minute DataFrame
    withdrawals_per_minute_c_01 = pd.DataFrame(
        [
            {
                "minute": int(minute),
                "number": number,
                "perc_capacity": row["perc_capacity"],
                "seed": row["seed"],
            }
            for _, row in df[df["perc_capacity"] == 0.1].iterrows()
            for minute, number in row["withdrawals_per_minute"].items()
        ]
    ).sort_values(by=["minute", "seed"])
    withdrawals_per_minute_c_01["tx_smooth"] = (
        withdrawals_per_minute_c_01.groupby("seed")["number"]
        .rolling(window=window_size, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )

    # Plot deposits_per_minute/withdrawals_per_minute/submarine_swaps_per_minute on the first y-axis
    sns.lineplot(
        x="minute",
        y="tx_smooth",
        data=deposits_per_minute_c_01,
        estimator="mean",
        errorbar="sd",
        label="Waterfall",
        color="tab:green",
        ax=ax1,
    )
    sns.lineplot(
        x="minute",
        y="tx_smooth",
        data=withdrawals_per_minute_c_01,
        estimator="mean",
        errorbar="sd",
        color="tab:orange",
        label="Reverse Waterfall",
        ax=ax1,
    )
    sns.lineplot(
        x="minute",
        y="tx_smooth",
        hue="perc_capacity",
        data=submarine_swaps_per_minute,
        palette=blues,
        estimator="mean",
        errorbar="sd",
        ax=ax2,
    )

    # Create the legend for ax1
    ax1.legend()

    legend_labels = ["600k", "1.2M", "6M"]
    handles, labels = ax2.get_legend_handles_labels()
    ax2.legend(title="Network Liquidity (€)", handles=handles, labels=legend_labels)

    ax1.set_xticks(list(range(0, 1440, 60)))
    ax2.set_xticks(list(range(0, 1440, 60)))
    ax1.set_xticklabels([str(n) for n in range(24)])
    ax2.set_xticklabels([str(n) for n in range(24)])
    ax1.set_xlim(0, 1440)
    ax2.set_xlim(0, 1440)
    ax1.set_xlabel("")
    ax2.set_xlabel(r"\textbf{Hour of the Day}")
    ax1.set_ylabel(
        r"\begin{center}\textbf{(Rev)Waterfall}\\\textbf{per Minute}\end{center}"
    )
    ax2.set_ylabel(r"\begin{center}\textbf{Swaps}\\\textbf{per Minute}\end{center}")
    ax1.set_ylim(0, 130)

    plt.show()
    plt.tight_layout()
    fig.savefig(
        f"{args.output_dir}/withd_deposits_per_min.pdf",
        format="pdf",
        dpi=300,
        pad_inches=0,
        bbox_inches="tight",
    )
    plt.close(fig)


def route_len_plot(args: Args, df: pd.DataFrame) -> None:
    fig, ax = plt.subplots()
    fig.set_size_inches(8, 6)

    route_len_distr_df = pd.DataFrame(
        [
            {
                "value": int(value),
                "total": float(dictionary[DistributionInnerStats.TOTAL]),
                "routed_by_L1": float(dictionary[DistributionInnerStats.ROUTED_BY_L1]),
                "routed_by_L2": float(dictionary[DistributionInnerStats.ROUTED_BY_L2]),
            }
            for _, row in df.iterrows()
            for value, dictionary in row["route_length_distr"].items()
        ]
    )

    plot_df_pivot = route_len_distr_df.pivot_table(
        index=["value"], values=["routed_by_L1", "routed_by_L2"], fill_value=0
    ).reset_index()

    sns.barplot(
        data=plot_df_pivot,
        x="value",
        y="routed_by_L1",
        label="Routed By L1",
        estimator="mean",
        errorbar="sd",
    )

    sns.barplot(
        data=plot_df_pivot,
        x="value",
        y="routed_by_L2",
        label="Routed By L2",
        estimator="mean",
        errorbar="sd",
    )
    ax.set_xlabel("Number of hops")
    ax.set_ylabel("Count")
    plt.show()
    plt.tight_layout()

    fig.savefig(f"{args.output_dir}/route_len_distr.pdf", format="pdf", pad_inches=0)
    plt.close(fig)


def _read_payments_output_files(input_dir: Path) -> pd.DataFrame:
    """Read the payments_output_*.csv files"""
    logging.info("Reading input directory %s", input_dir)
    payments_output_files = sorted(input_dir.glob("payments_output_*.csv"))
    logging.info(
        "Reading files:\n%s", "\n".join(file.name for file in payments_output_files)
    )
    all_payments_df = pd.concat(
        (pd.read_csv(f) for f in payments_output_files), ignore_index=True
    ).sort_values(by=["id"])
    return all_payments_df


def ecdf(data):
    """Compute ECDF for a one-dimensional array of measurements."""
    n = len(data)
    x = np.sort(data)
    y = np.arange(1, n + 1) / n
    return x, y


def plot_time_ecdf(args: Args, path: Path) -> None:
    my_dataframes = []
    max_n_payments = 900000
    for subdirectory in path.rglob("*/capacity-0.01000/*"):
        payments_df = _read_payments_output_files(subdirectory)
        tx_only = payments_df[payments_df["type"] == 0]
        tx_only["time"] = tx_only["end_time"] - tx_only["start_time"]
        tx_only = tx_only[:max_n_payments]
        sampled_df = tx_only.iloc[::500, :]
        my_dataframes.append(sampled_df)

    ecdf_dataframes = [ecdf(df["time"]) for df in my_dataframes]
    mean_x = np.mean([row[0] for row in ecdf_dataframes], axis=0)
    mean_y = np.mean([row[1] for row in ecdf_dataframes], axis=0)
    mean_x = np.insert(mean_x, 0, 0)
    mean_x = np.insert(mean_x, len(mean_x), 2500)
    mean_y = np.insert(mean_y, 0, 0)
    mean_y = np.insert(mean_y, len(mean_y), 1)

    fig, ax = plt.subplots()
    fig.set_size_inches(6.5, 4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)

    plt.step(
        mean_x,
        mean_y,
        where="post",
        color="tab:blue",
        linewidth=2,
        label="Mean ECDF",
        zorder=1,
    )

    l1 = ax.lines[0]
    x1 = l1.get_xydata()[:, 0]
    y1 = l1.get_xydata()[:, 1]
    ax.fill_between(x1, y1, color="gray", alpha=0.2)
    ax.set_xlim(0, x1[-1])
    ax.set_ylim(-0.01, 1.01)
    ax.yaxis.set_major_formatter(
        ticker.PercentFormatter(xmax=1, decimals=0, is_latex=True)
    )
    ax.set_ylabel(
        r"\begin{center}\textbf{Percentage of payments}\\\textbf{routed successfully}\end{center}",
        fontsize=16,
    )
    ax.set_xlabel(r"\textbf{Time (ms)}", fontsize=16)
    plt.show()
    plt.tight_layout()
    fig.savefig(
        f"{args.output_dir}/time_ecdf.pdf",
        format="pdf",
        pad_inches=0,
        bbox_inches="tight",
    )
    plt.close(fig)


def plot4(args: Args, df: pd.DataFrame) -> None:
    # PLOT 4. - cost of locked liquidity
    fig, ax = plt.subplots()
    fig.set_size_inches(11, 6)

    sns.lineplot(
        data=df,
        x="wholesale_capacity",
        y="total_cost",
        marker="o",
        linestyle="-",
        color="tab:orange",
        errorbar="sd",
        estimator="mean",
        alpha=1,
        label="Total channel cost",
    )
    p = sns.lineplot(
        data=df,
        x="wholesale_capacity",
        y="cost_submarine_swaps",
        marker="o",
        linestyle="--",
        color="tab:blue",
        errorbar="sd",
        estimator="mean",
        alpha=1,
        label="Cost of swaps",
    )
    sns.lineplot(
        data=df,
        x="wholesale_capacity",
        y="cost_wholesale_liquidity",
        marker="o",
        linestyle="--",
        color="tab:green",
        errorbar="sd",
        estimator="mean",
        alpha=1,
        label="Cost of liquidity",
    )

    plt.legend(loc="lower left", bbox_to_anchor=(-0.01, 0.14))

    ax2 = ax.twinx()
    sns.lineplot(
        data=df,
        ax=ax2,
        x="wholesale_capacity",
        y="success",
        marker="o",
        linestyle=":",
        color="gray",
        errorbar="sd",
        estimator="mean",
        alpha=1,
        label="Payment success rate",
    )
    ax.set_ylabel(r"\textbf{Daily Cost of Channels Management}")
    ax.set_ylim(0, 800)
    # ax.ticklabel_format(axis='y', style='sci', scilimits=(0,0))
    # ax.set_yscale('log')
    y_major_ticks = [0, 200, 400, 600, 800]
    y_custom_labels = ["0", "200", "400", "600", "800"]
    ax.yaxis.set_major_locator(ticker.FixedLocator(y_major_ticks))
    ax.yaxis.set_major_formatter(ticker.FixedFormatter(y_custom_labels))

    ax2.set_ylabel(r"\textbf{Payment Success Rate}")
    ax2.set_ylim(0.8, 1.003)
    # y_minor_ticks=[0.1, 0.5, 0.8, 0.9, 0.95, 1]
    y_minor_ticks = [0.975, 1]
    ax2.yaxis.set_major_locator(ticker.FixedLocator(y_minor_ticks))
    ax2.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1, decimals=1))
    ax2.yaxis.set_minor_formatter(ticker.PercentFormatter(xmax=1, decimals=0))

    ax.set_xlabel(r"\textbf{Total Network Liquidity}")
    ax.set_xscale("symlog", linthresh=10000)
    ax.set_xlim(60e3, 12.02e6)
    major_ticks = [60e3, 120e3, 300e3, 600e3, 1.2e6, 3e6, 6e6, 12e6]
    custom_labels = ["60k", "120k", "300k", "600k", "1.2M", "3M", "6M", "12M"]
    ax.xaxis.set_major_locator(ticker.FixedLocator(major_ticks))
    ax.xaxis.set_major_formatter(ticker.FixedFormatter(custom_labels))

    p.axvspan(60e3, 600e3, color="grey", alpha=0.2)
    plt.tight_layout()
    plt.legend(loc="lower left", bbox_to_anchor=(-0.01, 0.06))
    fig.savefig(
        f"{args.output_dir}/cost_of_liquidity.pdf",
        format="pdf",
        pad_inches=0,
        bbox_inches="tight",
    )
    plt.close(fig)


def _do_job(args: Args) -> None:
    data_list = []
    for subdirectory in args.input_dir.rglob("*"):
        if subdirectory.is_dir():
            # Check if the subdirectory contains 'cloth_output.json' and the parent directory contains 'info.txt'
            info_input_path = subdirectory.parent.parent.parent / "info.txt"
            cloth_output_path = subdirectory / "cloth_output.json"
            if info_input_path.exists() and cloth_output_path.exists():
                # Process the subdirectory and append the data dictionary to the list
                data_list.append(process_directory(subdirectory))

    if len(data_list) == 0:
        logging.info("No simulation data found.")
        exit(EXIT_FAILURE)

    # Create a Pandas DataFrame from the list of dictionaries
    df = pd.DataFrame(data_list)
    # Define the LaTeX preamble with the font package and settings
    # Define the LaTeX preamble with the font package and settings
    latex_preamble = r"""

\renewcommand{\bfdefault}{sb}  % Semibold weight
"""
    custom_params = {
        "grid.linestyle": "--",
        "text.usetex": True,
        "text.latex.preamble": latex_preamble,
        "font.family": "serif",
        "font.size": 20,
        "legend.title_fontsize": 16,
        "axes.linewidth": 1.5,
        "lines.linewidth": 3,
        "axes.labelsize": 20,
        "xtick.labelsize": 18,
        "ytick.labelsize": 18,
        "legend.fontsize": 16,
        "lines.markersize": 8,
    }
    sns.set_theme(style="whitegrid", rc=custom_params)
    plot1(args, df[(df["nb_nodes"] == 4) & (df["tps"] == "constant")])
    plot3(
        args,
        df[
            (df["nb_nodes"] == 4)
            & (df["tps"] == "peak")
            & (df["rebal_mode"] == "rev-waterfall and swaps")
        ],
    )
    route_len_plot(
        args,
        df[
            (df["nb_nodes"] == 4)
            & (df["tps"] == "constant")
            & (df["perc_capacity"] == 1)
            & (df["rebal_mode"] == "rev-waterfall and swaps")
        ],
    )
    plot_time_ecdf(
        args, Path("/home/ubuntu/brain_camera_ready/results/peak_load_full_rebal/")
    )
    plot4(
        args,
        df[
            (df["nb_nodes"] == 4)
            & (df["tps"] == "constant")
            & (df["rebal_mode"] == "rev-waterfall and swaps")
        ],
    )


def _execute(args: Args) -> None:
    configure_logging(False)
    # Validate input directory
    check_path_is_directory(args.input_dir, CliArgsValidationError)

    # Validate output directory. Create it if it does not exist.
    args.output_dir.mkdir(parents=True, exist_ok=True)
    check_path_is_directory(args.output_dir, CliArgsValidationError)

    logging.info("CLoTH Statistics Plotter")
    logging.info("Arguments: %s", args.print_args())
    _do_job(args)


def main() -> None:
    # TODO: Aggiungere frequencies in tx/s per deposits, withdrawals e submarine swaps
    # Iterate through subdirectories in the input directory
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
