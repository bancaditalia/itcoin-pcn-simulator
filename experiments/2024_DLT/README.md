
### Introduction

Welcome to the GitHub repository for the short paper submitted to the Distributed Ledger Technologies (DLT24) workshop. This repository contains the code and data necessary to reproduce the results presented in the paper titled "Impact of Layer-1 Characteristics on Scalability of Layer-2 Semi-Hierarchical Payment Channel Networks".

The paper investigates the impact of Layer-1 blockchain characteristics on the scalability of Layer-2 Semi-Hierarchical payment channel networks (SH-PCNs). It highlights the importance of assessing scalability for efficient blockchain-based payment systems, such as Central Bank Digital Currencies (CBDCs). Utilizing a Parallel Discrete Event Simulator (PDES) for SH-PCNs, the authors assess how blockchain congestion, throughput, and latency influence the payment success rate of SH-PCNs.

### Reproducing Plots

To reproduce the plots presented in the paper without running any simulations, follow these instructions:

1. Run jupyter notebook

    ```
    cd ~/itcoin-pcn-simulator/utilities
    poetry shell
    cd ~/itcoin-pcn-simulator
    jupyter notebook
    ```

2. Open and run the DLT24 notebook (DLT24.ipynb)

3. Follow the content of the notebook to reproduce topologies, simulations and plots. You'll find the generated plots within the plots folder.
