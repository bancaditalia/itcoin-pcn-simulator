#ifndef CLOTH_ROSS_TX_GENERATION_H
#define CLOTH_ROSS_TX_GENERATION_H

#include "pcn_node.h"
#include "../features/payments.h"

/*
 * The load shaping algorithm will divide the total simulation time in
 * TPS_CFG_MAX_ROWS intervals. For each interval, a constant load will be
 * generated.
 *
 * 96 was chosen because for a 24 h simulation, each row will result in a 15
 * minutes interval.
 */
#define TPS_CFG_MAX_ROWS (96)

#define RETRY_GENERATE_RANDOM_MAX_OFFSET 3000

// Transaction state struct per PE
struct tx_generator_state {
  unsigned int rollback_count;
  double target_payment_rate[TPS_CFG_MAX_ROWS];
};

void schedule_next_generate_payment(tw_lp *lp, unsigned int routing_latency, unsigned int pmt_delay);

void generate_next_random_payment(node *sender, tw_bf *bf, message *in_msg, tw_lp *lp);

void rollback_withdrawal_if_any(tw_bf *bf, message *in_msg, tw_lp *lp);

void init_node_indexes_per_pe();

void init_tx_generator_state_per_pe();

void finalize_node_indexes_per_pe();

void finalize_node_pending_payments();

#endif // CLOTH_ROSS_TX_GENERATION_H
