from enum import Enum
from typing import List
import pandas as pd
import numpy as np
import os

class COLS(str, Enum):
    BLOCK_HEIGHT = 'block.height'
    BLOCK_TIME = 'block.time'
    SWAP_LATENCY = "swap.latency"
    TX_AMOUNT = 'tx.amount'
    TX_RECEIVER = 'tx.receiver'
    TX_START_TIME = 'tx.start_time'
    TX_SENDER = 'tx.sender'
    TX_TYPE = 'tx.type'

def _df_from_blockchain_output(path: str | os.PathLike) -> pd.DataFrame:
  blockchain_df = pd.read_csv(path)
  blockchain_df.columns = blockchain_df.columns.str.replace(' ', '')
  blockchain_df = blockchain_df.replace(r'^\s*$', np.nan, regex=True)
  blockchain_df[COLS.BLOCK_TIME] = pd.to_numeric(blockchain_df[COLS.BLOCK_TIME])
  blockchain_df[COLS.TX_START_TIME] = pd.to_numeric(blockchain_df[COLS.TX_START_TIME])
  return blockchain_df

def _add_swap_latencies_to_blockchain_df(blockchain_df: pd.DataFrame) -> pd.DataFrame:
  prepare_htlcs = blockchain_df[blockchain_df[COLS.TX_TYPE].str.contains("PREPARE_HTLC")]
  claim_htlcs = blockchain_df[blockchain_df[COLS.TX_TYPE].str.contains("CLAIM_HTLC")]
  columns_of_interest = [COLS.TX_TYPE, COLS.TX_SENDER, COLS.TX_RECEIVER, COLS.TX_AMOUNT, COLS.BLOCK_HEIGHT]

  merged = prepare_htlcs[columns_of_interest + [COLS.TX_START_TIME]].merge(claim_htlcs[columns_of_interest + [COLS.BLOCK_TIME]],
      how='left',
      on=[COLS.TX_SENDER, COLS.TX_RECEIVER, COLS.TX_AMOUNT],
      suffixes=['_prepare', '_claim'],
      validate='one_to_one'
  )
  # If the above one_to_one validation fails, something like the following may be needed: merged.groupby(['tx.sender', 'tx.receiver', 'tx.amount']).first().reset_index()
  merged = merged.dropna(
      how="any",
      subset=[COLS.BLOCK_HEIGHT+'_claim', COLS.BLOCK_TIME]
  )
  merged[COLS.SWAP_LATENCY] = merged[COLS.BLOCK_TIME] - merged[COLS.TX_START_TIME]
  return merged

def get_swap_latencies_from_blockchain_output(blockchain_output: str | os.PathLike) -> List:
  blockchain_df = _df_from_blockchain_output(blockchain_output)
  blockchain_df_with_latencies = _add_swap_latencies_to_blockchain_df(blockchain_df)
  return blockchain_df_with_latencies[COLS.SWAP_LATENCY].to_list()