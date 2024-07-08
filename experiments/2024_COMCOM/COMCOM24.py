import sys, os
from datetime import datetime
import pandas as pd
import numpy as np
import shutil
import pathlib

experiment_root_dir = os.path.abspath(os.path.join(os.getcwd()))
cloth_root_dir = os.path.abspath(os.path.join(os.getcwd(),"../.."))
cloth_root_dir, experiment_root_dir

from statistics_analyzer.blockchain import _df_from_blockchain_output, _add_swap_latencies_to_blockchain_df, get_swap_latencies_from_blockchain_output

BC_OUTPUT_FILE =  os.path.abspath(os.path.join(cloth_root_dir,"experiments/2024_COMCOM/results/exp-1/SH_PCN/20240705121632062-HT2VO/blockchain_output_0.csv"))

blockchain_df = _df_from_blockchain_output(BC_OUTPUT_FILE)

merged = _add_swap_latencies_to_blockchain_df(blockchain_df)

