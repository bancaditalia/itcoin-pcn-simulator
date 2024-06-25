#ifndef _blockchain_h
#define _blockchain_h

#include <ross.h>
#include "message.h"

typedef enum blockchain_tx_type {
  PREPARE_HTLC,
  CLAIM_HTLC
} blockchain_tx_type;

typedef struct blockchain_tx {
  blockchain_tx_type type;
  long sender;
  long receiver;
  long amount;
  double start_time;
  long originator;
} blockchain_tx;

typedef struct block {
  double confirmation_time;
  struct array* transactions; // Array of blockchain_tx
} block;

typedef struct blockchain {
  struct array* mempool;
  struct array* blocks; // Array of block
} blockchain;

// Event functions
void blockchain_init(blockchain *s, tw_lp *lp);
void blockchain_forward(blockchain *s, tw_bf *bf, message *in_msg, tw_lp *lp);
void blockchain_reverse(blockchain *s, tw_bf *bf, message *in_msg, tw_lp *lp);
void blockchain_commit(blockchain *s, tw_bf *bf, message *in_msg, tw_lp *lp);
void blockchain_final(blockchain *s, tw_lp *lp);

// Serialization and deserialization functions
void serialize_blockchain_tx(blockchain_tx* tx, char* serialized);
blockchain_tx* deserialize_blockchain_tx(const char* serialized);

const char* getTxType(blockchain_tx_type type);

#endif
