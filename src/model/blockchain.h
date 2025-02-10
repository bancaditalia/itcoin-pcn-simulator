#ifndef _blockchain_h
#define _blockchain_h

#include <ross.h>

struct message;

typedef enum blockchain_tx_type {
  PREPARE_HTLC,
  CLAIM_HTLC
} blockchain_tx_type;

struct blockchain_tx {
  blockchain_tx_type type;
  long sender;
  long receiver;
  long amount;
  double start_time;
  long originator;
};

struct blockchain {
  struct array* mempool;
  struct array* blocks; // Array of arrays of blockchain_tx
};

// Event functions
void blockchain_init(struct blockchain *s, tw_lp *lp);
void blockchain_forward(struct blockchain *s, tw_bf *bf, struct message *in_msg, tw_lp *lp);
void blockchain_reverse(struct blockchain *s, tw_bf *bf, struct message *in_msg, tw_lp *lp);
void blockchain_commit(struct blockchain *s, tw_bf *bf, struct message *in_msg, tw_lp *lp);
void blockchain_final(struct blockchain *s, tw_lp *lp);

// Serialization and deserialization functions
void serialize_blockchain_tx(struct blockchain_tx* tx, char* serialized);
struct blockchain_tx* deserialize_blockchain_tx(const char* serialized);

const char* getTxType(blockchain_tx_type type);

#endif
