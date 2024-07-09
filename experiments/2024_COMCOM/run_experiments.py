#!/usr/bin/env python

import itertools
from pathlib import Path

from experiments_runner import RebalancingMode, run_all_simulations
from plasma_network_generator.commands.generate_all import (
    DEFAULT_FRACTION_OF_UNBANKED_RETAIL_USERS,
)
from plasma_network_generator.commands.generate_all import (
    Args as TopologyGeneratorArgs,
)
from plasma_network_generator.commands.generate_all import (
    _execute as topology_generate,
)
from plasma_network_generator.core import select_eurosystem_subset
from plasma_network_generator.utils import TopologyType, get_topology_dir

MY_DIR = Path(__file__).resolve().parent
cloth_root_dir = MY_DIR.parent.parent


def setup_topology_directories() -> tuple[Path, Path]:
    """
    Set up and return the necessary topology directory paths.
    """
    topologies_dir = MY_DIR / "topologies"
    topologies_dir.mkdir(parents=True, exist_ok=True)
    return topologies_dir


def setup_result_directories() -> tuple[Path, Path]:
    """
    Set up and return the necessary result directory paths.
    """
    results_dir = MY_DIR / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    results_file = results_dir / "results.csv"
    return results_dir, results_file


def generate_topologies(
    topologies_dir: Path,
    seeds: list[int],
    capacities: list[float],
    topology_types: list[TopologyType],
) -> None:
    """
    Generate topologies for the given seeds and capacities.
    """
    for topology_type, seed in itertools.product(topology_types, seeds):
        # Check if topology dir already exists
        topology_type_seed_dir = get_topology_dir(topologies_dir, topology_type, seed)
        if topology_type_seed_dir.exists():
            print(f"Skipping {topology_type_seed_dir} because it already exists.")
            continue
        # Create topology dir
        topology_type_seed_dir.mkdir(parents=True, exist_ok=True)
        # Generate topologies
        topgen_args = TopologyGeneratorArgs(
            model_params_file=MY_DIR / "PCN_model_params.json",
            nb_partitions=[4],
            seed=seed,
            nations=select_eurosystem_subset(["IT", "CY", "FI"]),
            nb_cb=0 if topology_type == TopologyType.SF_PCN else 3,
            nb_retail=300000,
            nb_merchants=3000,
            nb_intermediaries=30,
            capacity_fractions=capacities,
            output_dir=topology_type_seed_dir,
            # Other args
            version=False,  # Do not print version and exit
            verbose=False,
            p_small_merchants=0.4,
            p_medium_merchants=0.3,
            p_large_merchants=0.3,
            fraction_of_unbanked_retail_users=DEFAULT_FRACTION_OF_UNBANKED_RETAIL_USERS,
            scale_free_2_2=(topology_type == TopologyType.SF_PCN),
        )
        topology_generate(topgen_args)


def run_experiment_1() -> None:
    topology_types = [t for t in TopologyType]
    seeds = [
        7,
        13,
        23,
        42,
        45,
    ]
    capacities = [
        0.0,
        0.00001,
        0.00002,
        0.00005,
        0.0001,
        0.0002,
        0.0005,
        0.001,
        0.0013,
        0.0015,
        0.0018,
        0.002,
        0.005,
        0.01,
        0.02,
        0.05,
        0.1,
        1.0,
    ]
    # Topology generation
    topologies_dir = setup_topology_directories()
    generate_topologies(topologies_dir, seeds, capacities, topology_types)
    # Run experiments
    # Experiment 1 (Plot 1...2)
    results_dir, results_file = setup_result_directories()
    results = run_all_simulations(
        cloth_root_dir=cloth_root_dir,
        experiment_number=1,
        topologies_dir=topologies_dir,
        results_dir=results_dir,
        results_file=results_file,
        block_congestion_rates=0,
        block_sizes=4,
        capacities=capacities,
        num_processess=4,
        seeds=seeds,
        simulation_ends=86400000,
        submarine_swap_thresholds=0.9,
        rebalancing=[RebalancingMode.NONE, RebalancingMode.REV, RebalancingMode.FULL],
        use_known_paths=1,
        syncs="5 --max-opt-lookahead=100 --batch=1",
        topology_types=topology_types,
        tpss=2,
        tps_cfgs=None,
        cleanup=False,
    )


def run_experiment_2() -> None:
    topology_types = [t for t in TopologyType]
    seeds = [
        7,
        13,
        23,
        42,
        45,
    ]
    capacities = [
        0.00100,
        0.00200,
        0.00500,
    ]
    # Topology generation
    topologies_dir = setup_topology_directories()
    generate_topologies(topologies_dir, seeds, capacities, topology_types)
    # Run experiments
    # Experiment 2 (Plot 3)
    results_dir, results_file = setup_result_directories()
    results = run_all_simulations(
        cloth_root_dir=cloth_root_dir,
        experiment_number=1,
        topologies_dir=topologies_dir,
        results_dir=results_dir,
        results_file=results_file,
        block_congestion_rates=0,
        block_sizes=4,
        capacities=capacities,
        num_processess=4,
        seeds=seeds,
        simulation_ends=86400000,
        submarine_swap_thresholds=0.9,
        rebalancing=[RebalancingMode.FULL],
        use_known_paths=1,
        syncs="5 --max-opt-lookahead=100 --batch=1",
        topology_types=topology_types,
        tpss=None,
        tps_cfgs=MY_DIR / "PCN_load.txt",
        cleanup=False,
    )


def main() -> None:
    run_experiment_1()


if __name__ == "__main__":
    main()
