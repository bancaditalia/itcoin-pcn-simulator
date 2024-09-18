# The itCoin Payment Channel Networks Simulator

The itCoin Payment Channel Network (PCN) Simulator is based on a combination of [CloTH](https://github.com/marcono/cloth), a state-of-the-art simulator of the Lightning Network, and [ROSS](https://github.com/ross-org/ROSS), a framework for parallel discrete event simulations.
The target topology for the simulator is a [Semi-Hierarchical PCN](https://arxiv.org/pdf/2401.11868), a special topology based on a three-tier structure that corresponds to the traditional financial system. The repo also includes a topology generator for Semi-Hierarchical PCNs.

## Installing requirements

* Python 3.11 (with dev/distutils)
* Poetry: please, follow the [official installation instructions](https://python-poetry.org/docs/).
* [openmpi](https://docs.open-mpi.org/en/v5.0.x/installing-open-mpi/quickstart.html)

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
    cmake ..
    make
    ```

## Generating a topology

To generate network topologies, follow these steps:

1. Set up the poetry environment:

    ```bash
    cd ~/itcoin-pcn-simulator/utilities
    poetry env use python3.11
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
        --size "3 30 30k 3k" \
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
    * `--cloth-input-file`: path to the CLoTH input file
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
    mkdir -p "${OUTDIR}"

    NP=4 && \
    INDIR="experiments/workspace/topologies/seed_42/capacity-0.5/k_0${NP}" && \
    mpirun -np $NP build/itcoin-pcn-simulator \
        --input-dir=${INDIR} \
        --output-dir=${OUTDIR} \
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
    OUTDIR="${OUTDIR}" poetry shell

    python statistics_analyzer/commands/analyzer.py \
        --input-dir ../"${OUTDIR}" \
        --output-dir ../"${OUTDIR}"
    ```

## More advances examples

For more advanced examples and simulations, see the following files:

* [DLT24 notebook](experiments/2024_DLT/DLT24.ipynb)
