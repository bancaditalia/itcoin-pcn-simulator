import itertools
import json
import pathlib
import random
import string
import subprocess
from datetime import datetime
from enum import Enum
from typing import Literal, assert_never

import numpy as np
import pandas as pd

from statistics_analyzer.commands.analyzer import Args as Statistics_analyzer_args
from statistics_analyzer.commands.analyzer import _execute as statistics_analyze


class RebalancingMode(Enum):
    FULL = "Full"
    REV = "Rev"
    NONE = "None"


def select_rebalancing_mode(
    rebalancing_mode: RebalancingMode,
) -> tuple[Literal[0, 1], Literal[0, 1], Literal[0, 1]]:
    if rebalancing_mode == RebalancingMode.FULL:
        return 1, 1, 1
    if rebalancing_mode == RebalancingMode.REV:
        return 1, 1, 0
    if rebalancing_mode == RebalancingMode.NONE:
        return 0, 0, 0
    assert_never(rebalancing_mode)


def cleanup_pcn_simulation(output_dir: pathlib.Path, simulation_log_file: str) -> None:
    for f in output_dir.glob("node_logs_file_*.txt"):
        f.unlink()
    for f in output_dir.glob("edges_output_*.csv"):
        f.unlink()
    for f in output_dir.glob("nodes_output_*.csv"):
        f.unlink()
    for f in output_dir.glob("payments_output_*.csv"):
        f.unlink()
    for f in output_dir.glob("channels_output_*.csv"):
        f.unlink()
    (output_dir / simulation_log_file).unlink()

    # Remove everything
    # shutil.rmtree(output_dir)


def run_pcn_simulation(
    cloth_root_dir: pathlib.Path,
    topologies_dir: pathlib.Path,
    results_dir: pathlib.Path,
    seed: int,
    capacity: float,
    simulation_end: int,
    tps: int | None,
    tps_cfg: pathlib.Path | None,
    block_size: int,
    block_congestion_rate: float,
    submarine_swap_threshold: float,
    waterfall: Literal[0, 1],
    reverse_waterfall: Literal[0, 1],
    submarine_swaps: Literal[0, 1],
    simulation_log_file: str,
    sync: int,
    num_processes: int,
    cleanup: bool,
    verbose: bool,
) -> dict:
    # Calculate the input dir
    topologies_seed_dir = (topologies_dir / f"seed_{seed}").resolve()
    capacity_dir_name = f"capacity-{capacity}"
    input_dir = topologies_seed_dir / capacity_dir_name / f"k_0{num_processes}"
    if not input_dir.is_dir() and num_processes == 1:
        input_dir = topologies_seed_dir / capacity_dir_name / "k_04"

    # Calculate the output dir
    date_str = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    rand_str = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    output_dir = (results_dir / f"{date_str}-{rand_str}").resolve()

    # Ensure that exactly one between tps and tps_cfg is set
    tps_flag = tps is not None
    tps_cfg_flag = tps_cfg is not None
    assert tps_flag + tps_cfg_flag == 1, "Specify exactly one of tps or tps_cfg"

    # Create the output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prepare and execute the simulation command
    command = f"""
    cd {cloth_root_dir} && \
    mpirun -np {num_processes} build/itcoin-pcn-simulator \\
      --input-dir={input_dir} \\
      --output-dir={output_dir} \\
      --synch={sync} --extramem=400000 \\
      --waterfall={waterfall} --reverse-waterfall={reverse_waterfall} \\
      --submarine-swaps={submarine_swaps} \\
      --end={simulation_end} \\
      {f"--tps={tps}" if tps_flag else f"--tps-cfg={tps_cfg}"} \\
      --block-size={block_size} \\
      --block-congestion-rate={block_congestion_rate} \\
      --submarine-swap-threshold={submarine_swap_threshold}
    """
    verbose and print(command)
    try:
        with (output_dir / simulation_log_file).open(mode="w+") as logf:
            subprocess.run(
                command, shell=True, check=True, stdout=logf, stderr=logf, text=True
            )
    except subprocess.CalledProcessError as e:
        print("An error occurred while executing the script:", e.stderr)

    # Analyze results
    stat_analyzer_args = Statistics_analyzer_args(
        input_dir=output_dir,
        output_dir=output_dir,
        verbose=False,
        rank_idx=None,
    )
    statistics_analyze(stat_analyzer_args)

    # Create simulation results record
    cloth_output_file = (output_dir / "cloth_output.json").resolve()
    with cloth_output_file.open(mode="r") as f:
        cloth_output = json.load(f)

    DAILY_LIQUDITY_COST = 0.0001271488302
    SUBMARINE_SWAP_COST = 0.10 * 2
    cost_wholesale_liquidity = (
        DAILY_LIQUDITY_COST * float(cloth_output["TotalWholeSaleCapacity"]) / 100
    )
    cost_submarine_swaps = SUBMARINE_SWAP_COST * (
        float(cloth_output["TotalSubmarineSwaps1<>2"])
        + float(cloth_output["TotalSubmarineSwaps2<>2"])
    )

    simulation_result = {
        # Simulation inputs
        "block_congestion_rate": block_congestion_rate,
        "block_size": block_size,
        "seed": seed,
        "capacity": capacity,
        "num_processes": num_processes,
        "simulation_end": simulation_end,
        "tps": tps,
        "tps_cfg": str(tps_cfg),
        "submarine_swap_threshold": submarine_swap_threshold,
        "waterfall": waterfall,
        "reverse_waterfall": reverse_waterfall,
        "submarine_swaps": submarine_swaps,
        "sync": sync,
        # Simulation results
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
        "route_length_distr": json.dumps(cloth_output["RouteLengthDistr"]),
        "transactions_per_minute": json.dumps(cloth_output["TransactionsPerMinute"]),
        "success_per_minute": json.dumps(cloth_output["SuccessPerMinute"]),
        "deposits_per_minute": json.dumps(cloth_output["DepositsPerMinute"]),
        "withdrawals_per_minute": json.dumps(cloth_output["WithdrawalsPerMinute"]),
        "submarine_swaps_per_minute": json.dumps(
            cloth_output["SubmarineSwapsPerMinute"]
        ),
        "mean_submarine_swaps_per_minute": np.mean(
            np.array(
                list(cloth_output["SubmarineSwapsPerMinute"].values()), dtype=float
            )
        ),
        "cost_submarine_swaps": cost_submarine_swaps,
        "cost_wholesale_liquidity": cost_wholesale_liquidity,
        "total_cost": cost_wholesale_liquidity + cost_submarine_swaps,
    }

    # Cleanup
    if cleanup:
        cleanup_pcn_simulation(output_dir, simulation_log_file)

    return simulation_result


def run_all_simulations(
    cloth_root_dir: pathlib.Path,
    topologies_dir: pathlib.Path,
    results_dir: pathlib.Path,
    results_file: pathlib.Path,
    block_congestion_rates: float | list[float],
    block_sizes: int | list[int],
    capacities: float | list[float],
    num_processess: int | list[int],
    seeds: int | list[int],
    simulation_ends: int | list[int],
    submarine_swap_thresholds: float | list[float],
    rebalancing: RebalancingMode | list[RebalancingMode],
    syncs: int | list[int],
    tpss: int | list[int] | None,
    tps_cfgs: pathlib.Path | list[pathlib.Path] | None,
) -> pd.DataFrame:
    # Read existing experiments
    results = pd.DataFrame()
    if results_file.is_file():
        results = pd.read_csv(results_file)

    block_congestion_rates = (
        block_congestion_rates
        if isinstance(block_congestion_rates, list)
        else [block_congestion_rates]
    )
    block_sizes = block_sizes if isinstance(block_sizes, list) else [block_sizes]
    capacities = capacities if isinstance(capacities, list) else [capacities]
    num_processess = (
        num_processess if isinstance(num_processess, list) else [num_processess]
    )
    seeds = seeds if isinstance(seeds, list) else [seeds]
    simulation_ends = (
        simulation_ends if isinstance(simulation_ends, list) else [simulation_ends]
    )
    submarine_swap_thresholds = (
        submarine_swap_thresholds
        if isinstance(submarine_swap_thresholds, list)
        else [submarine_swap_thresholds]
    )
    rebalancing = rebalancing if isinstance(rebalancing, list) else [rebalancing]
    syncs = syncs if isinstance(syncs, list) else [syncs]
    # The following code fixes a potential bug: we can't simply pass "None" to
    # itertools.product(): its arguments must all be iterables.
    #
    # If we want to pass None for tpss or tps_cfgs, we have to wrap it.
    # We choose a tuple because it can be statically typed as an iterable
    # containing a _single_ literal None, whereas a list would have a variable
    # number of elements.
    tpss_iterable: list[int] | tuple[Literal[None]] = (
        (None,) if tpss is None else tpss if isinstance(tpss, list) else [tpss]
    )
    tps_cfgs_iterable: list[pathlib.Path] | tuple[Literal[None]] = (
        (None,)
        if tps_cfgs is None
        else tps_cfgs
        if isinstance(tps_cfgs, list)
        else [tps_cfgs]
    )

    for (
        block_congestion_rate,
        block_size,
        capacity,
        num_processes,
        seed,
        simulation_end,
        submarine_swap_threshold,
        rebalancing_mode,
        sync,
        tps,
        tps_cfg,
    ) in itertools.product(
        block_congestion_rates,
        block_sizes,
        capacities,
        num_processess,
        seeds,
        simulation_ends,
        submarine_swap_thresholds,
        rebalancing,
        syncs,
        tpss_iterable,
        tps_cfgs_iterable,
    ):
        # Define the simulation string
        simulation_string = f"{block_congestion_rate=}, {block_size=}, {capacity=}, {num_processes=}, {seed=}, {simulation_end=}, {submarine_swap_threshold=}, {rebalancing_mode.value=}, {tps=}, {tps_cfg=}, {sync=}"

        waterfall, reverse_waterfall, submarine_swaps = select_rebalancing_mode(
            rebalancing_mode
        )

        if (not results.empty) and (
            (results["block_congestion_rate"] == block_congestion_rate)
            & (results["block_size"] == block_size)
            & (results["capacity"] == capacity)
            & (results["num_processes"] == num_processes)
            & (results["seed"] == seed)
            & (results["simulation_end"] == simulation_end)
            & (results["submarine_swap_threshold"] == submarine_swap_threshold)
            & (results["waterfall"] == waterfall)
            & (results["reverse_waterfall"] == reverse_waterfall)
            & (results["submarine_swaps"] == submarine_swaps)
            & (
                (results["tps_cfg"] == tps_cfg)
                if tps_cfg is not None
                else (results["tps"] == tps)
            )
            & (results["sync"] == sync)
        ).any():
            print(f"Skipping {simulation_string}")
            continue
        print(f"Running {simulation_string}")

        simulation_log_file = "simulation_log.txt"
        simulation_result = run_pcn_simulation(
            cloth_root_dir=cloth_root_dir,
            topologies_dir=topologies_dir,
            results_dir=results_dir,
            seed=seed,
            capacity=capacity,
            simulation_end=simulation_end,
            tps=tps,
            tps_cfg=tps_cfg,
            block_size=block_size,
            block_congestion_rate=block_congestion_rate,
            submarine_swap_threshold=submarine_swap_threshold,
            waterfall=waterfall,
            reverse_waterfall=reverse_waterfall,
            submarine_swaps=submarine_swaps,
            simulation_log_file=simulation_log_file,
            sync=sync,
            num_processes=num_processes,
            cleanup=True,
            verbose=False,
        )

        results = pd.concat(
            [results, pd.DataFrame([simulation_result])], ignore_index=True
        )
        results.to_csv(results_file, index=False)

    return results
