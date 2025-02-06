
#ifndef _features_submarine_swaps_h
#define _features_submarine_swaps_h

#include <ross.h>

#include "payments.h"
#include "../model/blockchain.h"

typedef enum submarine_swap_state {
  REQUESTED,
  L1_PREPARED,
  L1_CLAIMED
} submarine_swap_state;

typedef struct submarine_swap {
  long submarine_sender;
  long submarine_receiver;
  long amount;
  long trigger_payment_id;
  double start_time;
  submarine_swap_state state;
} submarine_swap;

// Event handling functions
void submarine_swaps_on_forward_payment(tw_lp *lp, struct message *in_msg);
void submarine_swaps_on_forward_payment_rev(tw_lp *lp, struct message *in_msg);

void submarine_swaps_on_swap_request(tw_lp *lp, struct message *in_msg);
void submarine_swaps_on_swap_request_rev(tw_lp *lp, struct message *in_msg);

void submarine_swaps_on_blockchain_tx(tw_lp *lp, blockchain_tx* tx);
void submarine_swaps_on_blockchain_tx_rev(tw_lp *lp, blockchain_tx* tx);
void submarine_swaps_on_blockchain_tx_commit(tw_lp *lp, blockchain_tx* tx);

void submarine_swaps_on_receive_success(tw_lp *lp, struct payment* payment);
void submarine_swaps_on_receive_success_rev(tw_lp *lp, struct payment* payment);

// Serialization and deserialization functions
void serialize_submarine_swap(submarine_swap* tx, char* serialized);
submarine_swap* deserialize_submarine_swap(const char* serialized);

#endif

