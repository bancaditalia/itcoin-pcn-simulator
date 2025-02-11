# The itCoin Payment Channel Networks Simulator

The itCoin Payment Channel Network (PCN) Simulator is based on a combination of [CloTH](https://github.com/marcono/cloth), a state-of-the-art simulator of the Lightning Network, and [ROSS](https://github.com/ross-org/ROSS), a framework for parallel discrete event simulations.
The target topology for the simulator is a [Semi-Hierarchical PCN](https://arxiv.org/pdf/2401.11868), a special topology based on a three-tier structure that corresponds to the traditional financial system. The repo also includes a topology generator for Semi-Hierarchical PCNs.

## Installing requirements

* Python 3.11 or later (with dev/distutils)
* Poetry: please, follow the [official installation instructions](https://python-poetry.org/docs/).
* [OpenMPI](https://docs.open-mpi.org/en/v5.0.x/installing-open-mpi/quickstart.html)

  <details>
  <summary>OpenMPI howto on Fedora (click to open)</summary>
  If you are running <strong>Fedora</strong> you will need to execute once:
  
  ```
  dnf install openmpi-devel
  ```
  
  Also, **each time you open a new shell** to run the project you will need to
  activate the openmpi environment, running:
  ```
  source /etc/profile.d/modules.sh
  module load mpi/openmpi-x86_64
  ```
  </details>


## Cloning and building the simulator

1. Clone the `itcoin-pcn-simulator` repository:

    ```bash
    cd ~
    git clone https://github.com/bancaditalia/itcoin-pcn-simulator.git
    ```

2. Build the simulator:

    ```bash
    cd ~/itcoin-pcn-simulator
    mkdir build
    cd build
    cmake -DCMAKE_BUILD_TYPE=Release ..
    make
    ```

## Generating a topology

To generate network topologies, follow these steps:

1. Set up the poetry environment:

    ```bash
    cd ~/itcoin-pcn-simulator/utilities
    poetry shell
    PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring
    poetry install
    ```

2. Generate a topology. In this example, we create a topology representing three nations (Italy, Finland, Cyprus), each with proportions based on their real-world geographic sizes. Different topologies will be generated for each specified `--capacity-fractions`, using channel capacities defined in the `--model-params-file`. These topologies will be partitioned into the specified `-k` number of partitions, and the output will be stored in the `--output-dir`:

    ```bash
    cd ~/itcoin-pcn-simulator/utilities
    poetry shell
    mkdir -p ../experiments/workspace/topologies/seed_42

    python plasma_network_generator/commands/generate_all.py \
        -k 1 2 4 \
        --seed 42 \
        --size "3 30 30000 3000" \
        --nations "IT,FI,CY" \
        --capacity-fractions 0.5 1 \
        --model-params-file "plasma_network_generator/defaultModelParams.json" \
        --output-dir ../experiments/workspace/topologies/seed_42
    ```

## Running a simulation

1. Run the simulator. The ROSS Kernel requires the following parameters:

    * `-np`: number of processes (must match the number of partitions used to partition the topology)
    * `--synch`: synchronization method (options: 1=sequential, 2=conservative, 3=optimistic, 5=real-time optimistic)
    * `--end`: simulation end time (default 100000.00)

    Additionally, the model accepts these input parameters:
    * `--input-dir`: directory containing the files defining the simulation parameters. The simulation parameters are read from the following files: `plasma_network_channels.csv`, `plasma_network_edges.csv`, `plasma_network_nodes.csv`, `plasma_paths.csv`, which can be generated as described above
    * `--output-dir`: output directory where simulation results are stored (must exist)
    * `--tps`: constant load mode (transactions per second)
    * `--tps-config`: variable load mode (configured by a file)
    * `--waterfall`: enable/disable automatic deposits (1/0)
    * `--reverse-waterfall`: enable/disable automatic withdrawals (1/0)
    * `--submarine-swaps`: enable/disable on-chain vs off-chain atomic swaps (1/0)

    Sample command:
    ```bash
    cd ~/itcoin-pcn-simulator
    mkdir -p experiments/workspace/results

    OUTDIR="experiments/workspace/results/$(date +"%Y%m%d%H%M%S")"
    mkdir "${OUTDIR}"

    NP=4 && \
    INDIR="experiments/workspace/topologies/seed_42/capacity-0.5/k_0${NP}" && \
    mpirun -np $NP build/itcoin-pcn-simulator \
        --input-dir="${INDIR}" \
        --output-dir="${OUTDIR}" \
        --synch=3 --extramem=400000 \
        --max-opt-lookahead=100 --batch=1 \
        --waterfall=1 --reverse-waterfall=1 \
        --use-known-paths=1 \
        --submarine-swaps=1 \
        --end=86400000 \
        --tps=2 \
        --block-size=4 \
        --block-congestion-rate=0 \
        --submarine-swap-threshold=0.9
    ```

## Analyze results

1. You can calculate statistical about simulation results using the statistics analyzer utility. For example, after executing the following command, you will find the aggregated results in `cloth_output.json`

    ```bash
    cd ~/itcoin-pcn-simulator/utilities
    poetry shell

    python statistics_analyzer/commands/analyzer.py \
        --input-dir ../"${OUTDIR}" \
        --output-dir ../"${OUTDIR}"
    ```

## More advanced examples

For more advanced examples and simulations, see the following files:

* [DLT24 notebook (no longer supported: available on an earlier version)](https://github.com/bancaditalia/itcoin-pcn-simulator/blob/dlt24-v1/experiments/2024_DLT/DLT24.ipynb)
* the [COMCOM25 README.md](experiments/2025_COMCOM/README.md), and [COMCOM25 notebook](experiments/2025_COMCOM/COMCOM.ipynb)
