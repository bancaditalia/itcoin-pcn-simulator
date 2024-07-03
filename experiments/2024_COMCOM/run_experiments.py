from enum import Enum
from pathlib import Path

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


class TopologyType(Enum):
    SH_PCN = "SH_PCN"
    SF_PCN = "SF_PCN"


def setup_directories(topology_type: TopologyType) -> tuple[Path, Path]:
    """
    Set up and return the necessary directory paths.
    """
    cloth_root_dir = Path.cwd().parent.parent

    topologies_dir = (
        cloth_root_dir
        / "experiments"
        / "2024_COMCOM"
        / "topologies"
        / topology_type.value
    )
    topologies_dir.mkdir(parents=True, exist_ok=True)

    return cloth_root_dir, topologies_dir


def generate_topologies(
    cloth_root_dir: Path,
    topologies_dir: Path,
    seeds: list[int],
    capacities: list[float],
    topology_type: TopologyType,
) -> None:
    """
    Generate topologies for the given seeds and capacities.
    """
    for seed in seeds:
        topologies_seed_dir = topologies_dir / f"seed_{seed}"
        if topologies_seed_dir.exists():
            print(f"Skipping {topologies_seed_dir} because it already exists.")
            continue

        topgen_args = TopologyGeneratorArgs(
            model_params_file=cloth_root_dir
            / "experiments"
            / "2024_COMCOM"
            / "PCN_model_params.json",
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
            fraction_of_unbanked_retail_users=DEFAULT_FRACTION_OF_UNBANKED_RETAIL_USERS,
            scale_free_2_2=(topology_type == TopologyType.SF_PCN),
        )

        topology_generate(topgen_args)


def main() -> None:
    seeds = [7, 13, 23, 42, 45]
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

    for topology_type in TopologyType:
        cloth_root_dir, topologies_dir = setup_directories(topology_type)
        generate_topologies(
            cloth_root_dir, topologies_dir, seeds, capacities, topology_type
        )


if __name__ == "__main__":
    main()
