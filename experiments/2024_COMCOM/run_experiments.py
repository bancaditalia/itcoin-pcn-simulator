from pathlib import Path
from enum import Enum
from typing import Tuple, List
from experiments_runner import (run_all_simulations, RebalancingMode)
from plasma_network_generator.commands.generate_all import (
    Args as TopologyGeneratorArgs,
    _execute as topology_generate,
    DEFAULT_FRACTION_OF_UNBANKED_RETAIL_USERS
)
from plasma_network_generator.core import select_eurosystem_subset

class TopologyType(Enum):
    SH_PCN = 'SH_PCN'
    SF_PCN = 'SF_PCN'

def setup_topology_directories(topology_type: TopologyType) -> Tuple[Path, Path]:
    """
    Set up and return the necessary topology directory paths.
    """
    cloth_root_dir = Path.cwd().parent.parent

    topologies_dir = cloth_root_dir / f"experiments/2024_COMCOM/topologies/{topology_type.value}"
    topologies_dir.mkdir(parents=True, exist_ok=True)

    return cloth_root_dir, topologies_dir

def setup_result_directories(experiment_nb: int, topology_type: TopologyType) -> Tuple[Path, Path]:
    """
    Set up and return the necessary result directory paths.
    """
    cloth_root_dir = Path.cwd().parent.parent

    results_dir = cloth_root_dir / f"experiments/2024_COMCOM/results/exp-{experiment_nb}/{topology_type.value}"
    results_dir.mkdir(parents=True, exist_ok=True)

    results_file = results_dir / "results.csv"

    return results_dir, results_file

def generate_topologies(cloth_root_dir: Path, topologies_dir: Path, seeds: List[int], capacities: List[float], topology_type: TopologyType) -> None:
    """
    Generate topologies for the given seeds and capacities.
    """
    for seed in seeds:
        topologies_seed_dir = topologies_dir / f"seed_{seed}"
        if topologies_seed_dir.exists():
            print(f"Skipping {topologies_seed_dir} because it already exists.")
            continue

        topgen_args = TopologyGeneratorArgs(
            model_params_file=cloth_root_dir / "experiments/2024_COMCOM/PCN_model_params.json",
            nb_partitions=[4],
            seed=seed,
            nations=select_eurosystem_subset(["IT", "CY", "FI"]),
            nb_cb=0 if topology_type == TopologyType.SF_PCN else 3,
            nb_retail=300000,
            nb_merchants=3000,
            nb_intermediaries=30,
            capacity_fractions=capacities,
            output_dir=topologies_seed_dir,
            # Other args
            version=False,  # Do not print version and exit
            verbose=False,
            p_small_merchants=0.4,
            p_medium_merchants=0.3,
            p_large_merchants=0.3,
            fraction_of_unbanked_retail_users = DEFAULT_FRACTION_OF_UNBANKED_RETAIL_USERS,
            scale_free_2_2=True if topology_type == TopologyType.SF_PCN else False
        )

        topology_generate(topgen_args)

def run_experiment_1():
    seeds = [7, 13, 23, 42, 45]
    capacities = [0.0, 0.00001, 0.00002, 0.00005, 0.0001, 0.0002, 0.0005, 0.001, 0.0013, 0.0015, 0.0018, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 1.0]

    # Topology generation
    for topology_type in TopologyType:
        cloth_root_dir, topologies_dir = setup_topology_directories(topology_type)
        generate_topologies(cloth_root_dir, topologies_dir, seeds, capacities, topology_type)

    # Run experiments
    # Experiment 1 (Plot 1...2)
    for topology_type in TopologyType:
        cloth_root_dir, topologies_dir = setup_topology_directories(topology_type)
        results_dir, results_file = setup_result_directories(1, topology_type)
        results = run_all_simulations(
            cloth_root_dir = cloth_root_dir,
            topologies_dir = topologies_dir,
            results_dir = results_dir,
            results_file = results_file,
            block_congestion_rates = 0,
            block_sizes = 4,
            capacities = capacities,
            num_processess = 4,
            seeds = seeds,
            simulation_ends = 86400000,
            submarine_swap_thresholds = 0.9,
            rebalancing = [RebalancingMode.NONE, RebalancingMode.REV, RebalancingMode.FULL],
            use_known_paths = 1,
            syncs = "5 --max-opt-lookahead=100 --batch=1",
            tpss = 2,
            tps_cfgs = None,
            cleanup = False
        )

def main() -> None:
    run_experiment_1()

if __name__ == "__main__":
    main()