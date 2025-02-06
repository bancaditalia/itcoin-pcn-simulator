//The C driver file for a ROSS model
//This file includes:
// - an initialization function for each LP type
// - a forward event function for each LP type
// - a reverse event function for each LP type
// - a finalization function for each LP type

//Includes
#include <stdio.h>

#include "global.h"
#include "load.h"
#include "message.h"
#include "pcn_node.h"
#include "blockchain.h"

#include "../features/payments.h"
#include "../features/submarine_swaps.h"
#include "../features/routing.h"
#include "../features/htlc.h"
#include "../features/routing.h"

#include "../utils/array.h"
#include "../utils/logging.h"
#include "../utils/utils.h"

//Init function
// - called once for each LP
// ! LP can only send messages to itself during init !
void model_init (struct node *s, tw_lp *lp) {
  // init state data
  s = array_get(network->nodes, lp->gid);
  lp->cur_state = s;

  // NOTE: here we assume that only end uses are generating payments.
  if (s->type == END_USER) {
    // Create the first GENERATE_PAYMENT message to myself
    schedule_next_generate_payment(lp, 0, 0);
  }
}

// (USER) Forward event handler
void model_event (struct node *s, tw_bf *bf, struct message *in_msg, tw_lp *lp) {
  tw_clock start_time = tw_clock_read();
  // Init message fields that contain results of deserialization
  in_msg->payment = NULL;
  in_msg->tx = NULL;
  in_msg->swap = NULL;

  // initialize the bit field
  // bf->c0 = EDGE_UPDATED
  *(int *) bf = (int) 0;

  // Save the forward event handler time, that is used in the commit handler
  in_msg->fwd_handler_time = tw_now(lp);

  // Save the initial rng count
  long rng_start_count = lp->rng->count;

  // handle the message
  switch (in_msg->type) {
    case GENERATE_PAYMENT:
      generate_next_random_payment(s, bf, in_msg, lp);
      break;
    case FINDPATH : {
      in_msg->payment = deserialize_payment(in_msg->data);
      debug_node_forward(node_out_file, lp, in_msg);
      struct array* path = find_path(&global_router_state, in_msg->payment, tw_now(lp), network);
      if (path != NULL){
        // Here we would like to simulate the time required to run a findpath on the sender device
        tw_event *next_e = tw_event_new(in_msg->payment->sender, ROUTING_LATENCY, lp);
        struct message *next_msg = tw_event_data(next_e);
        generate_payment_route(in_msg->payment, path, network);
        array_free(path);
        next_msg->type = SENDPAYMENT;
        serialize_payment(in_msg->payment, next_msg->data);
        tw_event_send(next_e);
      }
      break;
    }
    case SENDPAYMENT: {
      in_msg->payment = deserialize_payment(in_msg->data);
      debug_node_forward(node_out_file, lp, in_msg);
      bf->c0 = send_payment(lp, in_msg->payment);
      break;
    }
    case FORWARDPAYMENT: {
      in_msg->payment = deserialize_payment(in_msg->data);
      debug_node_forward(node_out_file, lp, in_msg);
      bf->c0 = forward_payment(lp, in_msg->payment);
      submarine_swaps_on_forward_payment(lp, in_msg);
      break;
    }
    case RECEIVEPAYMENT: {
      in_msg->payment = deserialize_payment(in_msg->data);
      debug_node_forward(node_out_file, lp, in_msg);
      receive_payment(lp, in_msg->payment);
      break;
    }
    case FORWARDSUCCESS: {
      in_msg->payment = deserialize_payment(in_msg->data);
      debug_node_forward(node_out_file, lp, in_msg);
      forward_success(lp, in_msg->payment);
      break;
    }
    case RECEIVESUCCESS: {
      in_msg->payment = deserialize_payment(in_msg->data);
      debug_node_forward(node_out_file, lp, in_msg);
      receive_success(lp, in_msg->payment);
      submarine_swaps_on_receive_success(lp, in_msg->payment);
      break;
    }
    case FORWARDFAIL: {
      in_msg->payment = deserialize_payment(in_msg->data);
      debug_node_forward(node_out_file, lp, in_msg);
      forward_fail(lp, in_msg->payment);
      break;
    }
    case RECEIVEFAIL: {
      in_msg->payment = deserialize_payment(in_msg->data);
      debug_node_forward(node_out_file, lp, in_msg);
      receive_fail(lp, in_msg->payment);
      break;
    }
    case NOTIFYPAYMENT: {
      in_msg->payment = deserialize_payment(in_msg->data);
      debug_node_forward(node_out_file, lp, in_msg);
      notify_payment(lp, in_msg->payment);
      break;
    }
    case SWAP_REQUEST: {
      in_msg->swap = deserialize_submarine_swap(in_msg->data);
      debug_node_forward(node_out_file, lp, in_msg);
      submarine_swaps_on_swap_request(lp, in_msg);
      break;
    }
    case BC_TX_CONFIRMED: {
      in_msg->tx = deserialize_blockchain_tx(in_msg->data);
      debug_node_forward(node_out_file, lp, in_msg);
      submarine_swaps_on_blockchain_tx(lp, in_msg->tx);
      break;
    }
    default: {
      printf("Model: unhandeled forward message type %s\n", getEventName(in_msg->type));
      exit(-1);
    }
  }
  in_msg->rng_count = lp->rng->count - rng_start_count;
  in_msg->computation_time = (double) (tw_clock_read() - start_time) / g_tw_clock_rate;
}

//Reverse Event Handler
void model_event_reverse (struct node *s, tw_bf *bf, struct message *in_msg, tw_lp *lp) {
  debug_node_reverse(node_out_file, bf, lp, in_msg);

  // undo the state update using the value stored in the 'reverse' message
  // handle the message
  switch (in_msg->type) {
    case GENERATE_PAYMENT:
      rollback_withdrawal_if_any(bf, in_msg, lp);
      break;
    case FINDPATH : {
      break;
    }
    case SENDPAYMENT: {
      if(bf->c0){
        rev_send_payment(lp, in_msg->payment);
      }
      break;
    }
    case FORWARDPAYMENT: {
      if(bf->c0){
        rev_forward_payment(lp, in_msg->payment);
      }
      submarine_swaps_on_forward_payment_rev(lp, in_msg);
      break;
    }
    case RECEIVEPAYMENT: {
      rev_receive_payment(lp, in_msg->payment);
      break;
    }
    case FORWARDSUCCESS: {
      rev_forward_success(lp, in_msg->payment);
      break;
    }
    case RECEIVESUCCESS: {
      rev_receive_success(lp, in_msg->payment);
      submarine_swaps_on_receive_success_rev(lp, in_msg->payment);
      break;
    }
    case FORWARDFAIL: {
      rev_forward_fail(lp, in_msg->payment);
      break;
    }
    case RECEIVEFAIL: {
      rev_receive_fail(lp, in_msg->payment);
      break;
    }
    case NOTIFYPAYMENT: {
      rev_notify_payment(lp, in_msg->payment);
      break;
    }
    case SWAP_REQUEST: {
      in_msg->swap = deserialize_submarine_swap(in_msg->data);
      submarine_swaps_on_swap_request_rev(lp, in_msg);
      break;
    }
    case BC_TX_CONFIRMED: {
      in_msg->tx = deserialize_blockchain_tx(in_msg->data);
      submarine_swaps_on_blockchain_tx_rev(lp, in_msg->tx);
      break;
    }
    default :
      printf("Model: unhandeled reverse message type %d\n", in_msg->type);
  }

  // don't forget to undo all rng calls
  unsigned long rng_count = in_msg->rng_count;
  while(rng_count--){
    tw_rand_reverse_unif(lp->rng);
  }

  // Free the payment
  if (in_msg->payment != NULL)
    free_payment(in_msg->payment);
  if (in_msg->tx != NULL)
    free(in_msg->tx);
}

// (USER) Commit event handler
void model_commit (struct node *s, tw_bf *bf, struct message *in_msg, tw_lp *lp) {
  debug_node_commit(node_out_file, lp, in_msg);

  switch (in_msg->type) {
    case SENDPAYMENT: {
      // If we commit the SENDPAYMENT of an awaiting payment we can remove the awaiting payment
      if (s->rw_awaiting_payment != NULL && s->rw_awaiting_payment->id == in_msg->payment->id){
        // Delete the awaiting payment and exit
        free_payment(s->rw_awaiting_payment);
        s->rw_awaiting_payment = NULL;
        s->rw_withdrawal_id = 0;
      }
      break;
    }
    case RECEIVESUCCESS: {
      process_success_result(s, in_msg->payment, in_msg->fwd_handler_time);
      break;
    }
    case RECEIVEFAIL: {
      // Here, and in process_success_result above, we use the in_msg->fwd_handler_time instead of tw_now(lp)
      // Otherwise the next FINDPATH may fail because of result->fail_time > current_time (routing module)
      // Indeed, the COMMIT time for this RECEIVEFAIL event may be bigger than the FORWARD time of the next FINDPATH event
      // On the contrary, the FORWARD time of this RECEIVEFAIL event is not bigger than the FORWARD time of the next FINDPATH event
      process_fail_result(s, in_msg->payment, in_msg->fwd_handler_time);
      break;
    }
    case BC_TX_CONFIRMED: {
      submarine_swaps_on_blockchain_tx_commit(lp, in_msg->tx);
      break;
    }
  }

  // If it was a payment related event
  if (in_msg->payment!=NULL){
    // Populate the payment statistics
    if(in_msg->payment->end_time>0 && in_msg->payment->sender==lp->gid){
      node_payments_array = array_insert(node_payments_array, in_msg->payment);
    }
    else {
      // Free the payment
      free_payment(in_msg->payment);
    }
  }

  // Cleanup blockchain tx
  if (in_msg->tx != NULL) {
    free(in_msg->tx);
  }
}

//report any final statistics for this LP
int pe_header_written=0;
void model_final (struct node *s, tw_lp *lp){
  struct element *iterator;
  if(!pe_header_written++) {
    // Check for payments awaiting expired withdrawals
    // Temporarily here, this should become a WITHDRAWALFAIL event sent from the intermediary to the end user
    for(uint32_t i=0; i<array_len(network->nodes); i++){
      struct node* node = array_get(network->nodes, i);
      // Here shall we check if we have expired payments awaiting withdrawals
      if(node->rw_awaiting_payment != NULL && is_expired_payment(node->rw_awaiting_payment, tw_now(lp))) {
        // When expired we move into the final results
        set_expired_payment(node->rw_awaiting_payment, tw_now(lp));
        node_payments_array = array_insert(node_payments_array, node->rw_awaiting_payment);
        node->rw_awaiting_payment = NULL;
        node->rw_withdrawal_id = 0;
      }
    }
    write_output(network, node_payments_array, output_dir_name, g_tw_mynode);

    printf("TX GENERATOR STATE: LPs on PE %ld rolled back %d TXs\n", lp->pe->id, g_pe_tx_generator_state.rollback_count);

    finalize_node_pending_payments();
    finalize_node_indexes_per_pe();
  }
}

