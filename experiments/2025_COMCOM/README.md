# An Analysis of Pervasive Payment Channel Networks for Central Bank Digital Currencies - experiments and plots

Please refer to [the main README.md](../../README.md) to see how to build the
simulator and creating / activating the python environment necessary for the
analysis.

This document will assume that:
- all the prerequisites for building have been installed.
- the main simulator has been built in `<BASE_DIR>/build` via `cmake .. && make`
- the python virtual environment has been created via
  ```
  cd <BASE_DIR>/utilities
  poetry install
  poetry shell (or source $(poetry env activate) if you are using poetry 2.x)
  ```
- while keeping the virtualenv activated, you moved to the COMCOM directory via `cd <BASE_DIR>/experiments/2025_COMCOM`

## Executing the experiments or getting the results from the network

1. The experiments can be executed from scratch running `./run_experiments.py`.
   You will need ~500 GB of disk space and 3-4 days of computation;
2. Alternatively, a pre-packaged version of the original experiments can be
   downloaded from https://zenodo.org/records/14848786.
   To do this, you can run `./download-experiments-results.sh`. This will
   require ~400 MB of free disk space to download and extract.

Once you have executed 1. or 2., you will be able to start the notebook and generate the plots.

## Starting the notebook

Execute:
```
jupyter-notebook
```

And open `COMCOM.ipynb`.

In order to generate the plots, you will need to install some LaTeX packages,
detailed in the notebook.
