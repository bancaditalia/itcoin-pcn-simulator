#include "submarine_swaps.h"

#include "../utils/array.h"
#include "../model/global.h"
#include "../model/message.h"
#include "../model/pcn_node.h"
#include "../model/blockchain.h"
#include "../utils/logging.h"
#include "../features/payments.h"
#include "../features/network.h"
#include "../features/payments.h"
#include "../features/routing.h"
#include "../features/htlc.h"

void node_delete_swap(struct tw_lp* lp, submarine_swap* swap){
  struct node* node = lp->cur_state;
  // Search for a submarine swap that was started by this forward event
  for (int i=0; i<array_len(node->submarine_swaps); i++){
    submarine_swap* swap2 = array_get(node->submarine_swaps, i);
    // Delete if the swap was added
    if (swap2 == swap){ // Here pointer equaility is checked
      if (g_dbg_trace) {
        char lpstr[DEBUG_BUF_SIZE]; debug_lp("NODE", lp, lpstr);
        char objectstr[DEBUG_BUF_SIZE]; debug_submarine_swap(swap, objectstr);
        fprintf(node_out_file, "SS.c: %s deletes swap %s\n", lpstr, objectstr);
      }
      array_delete_element(node->submarine_swaps, i);
      break;
    }
  }
}

struct submarine_swap* node_find_swap_by_blockchain_tx(struct tw_lp* lp, struct blockchain_tx* tx){
  struct node* node = lp->cur_state;
  struct submarine_swap* swap = NULL;
  for (int i=0; i<array_len(node->submarine_swaps); i++){
    swap = array_get(node->submarine_swaps, i);
    if (
      swap->submarine_receiver==tx->sender &&
      swap->submarine_sender==tx->receiver &&
      swap->amount == tx->amount
    ) {
      break;
    }
    else {
      swap = NULL;
    }
  }
  if (g_dbg_trace && swap==NULL){
    // Here the swap has not been found, error
    char lpstr[DEBUG_BUF_SIZE]; debug_lp("NODE", lp, lpstr);
    char objectstr[DEBUG_BUF_SIZE]; debug_blockchain_tx(tx, objectstr);
    fprintf(node_out_file, "SS.c: %s cannot find swap by committed blockchain tx %s\n", lpstr, objectstr);
  }
  return swap;
}

struct submarine_swap* node_find_swap_by_submarine_payment(struct tw_lp* lp, struct payment* payment){
  struct node* node = lp->cur_state;
  struct submarine_swap* swap = NULL;
  for (int i=0; i<array_len(node->submarine_swaps); i++){
    swap = array_get(node->submarine_swaps, i);
    if (
      swap->submarine_receiver==payment->receiver &&
      swap->submarine_sender==payment->sender &&
      swap->amount == payment->amount
    ) {
      return swap;
    }
  }
  // Swap not found, error
  char objectstr[DEBUG_BUF_SIZE]; debug_payment(payment, objectstr);
  if (g_dbg_trace) {
    char lpstr[DEBUG_BUF_SIZE];
    debug_lp("NODE", lp, lpstr);
    fprintf(node_out_file, "SS.c: %s cannot find swap by payment %s\n", lpstr, objectstr);
  }
  printf("ERROR in submarine swaps: node %ld cannot find swap by payment %s\n", node->id, objectstr);
  exit(-1);
}


void submarine_swaps_on_forward_payment(tw_lp *lp, struct message *in_msg){
  // Get the payment
  struct payment* payment = in_msg->payment;

  /*
   * PrevNode 0 ------- PrevEdge with LOW balance ------> Node 1 ---->
   * PrevNode 0 <--- PrevBackwEdge with HIGH balance  --- Node 1
   * Not many payments can be routed from PrevNode to Node
   * Node will be the submarine sender, PrevNode the Receiver
   */

  struct node *node = lp->cur_state;
  struct route_hop* previous_route_hop = get_route_hop(node->id, payment->route->route_hops, 0);
  struct edge* prev_edge = array_get(network->edges,previous_route_hop->edge_id);
  struct edge* prev_backward_edge = array_get(network->edges, prev_edge->counter_edge_id);
  struct channel* prev_channel = array_get(network->channels, prev_edge->channel_id);
  struct node* prev_node = array_get(network->nodes, prev_edge->from_node_id);

  // Check atomic swap conditions on the previous edge
  // The previous edge is the receiving one, that may be filling
  double unbalancedness = 1.0 * prev_backward_edge->balance / prev_channel->capacity;
  if (g_dbg_trace){
    char lpstr[DEBUG_BUF_SIZE];
    debug_lp("NODE", lp, lpstr);
    fprintf(node_out_file, "SS.c: %s receiving from edge %ld with %ld of channel %ld with unbalancedness %f\n", lpstr, previous_route_hop->edge_id, prev_node->id, prev_channel->id, unbalancedness);
  }

  // The swap is:
  // Local node will send the submarine payment
  // Remote node will send the on-chain payment
  // Submarine sender will be local node id
  long submarine_sender = node->id;
  // Submarine receiver will be remote node id
  long submarine_receiver = prev_node->id;

  // Check if the swap was already started on this channel
  unsigned int submarine_swap_started = 0;
  for (int i=0; i<array_len(node->submarine_swaps); i++){
    submarine_swap* swap = array_get(node->submarine_swaps, i);
    if (swap->submarine_sender == submarine_sender && swap->submarine_receiver == submarine_receiver){
      submarine_swap_started=1;
      break;
    }
  }

  // Check if we can request the submarine swap
  unsigned int start_submarine_swap =
    !submarine_swap_started &&
    submarine_swaps_enabled &&
    (node->type == INTERMEDIARY || node->type == CB) &&
    (prev_node->type == INTERMEDIARY || prev_node->type == CB) &&
    unbalancedness > submarine_swap_threshold;

  if(!start_submarine_swap) return;
  // Else

  // Create swap
  in_msg->swap = malloc(sizeof(struct submarine_swap));
  submarine_swap* swap = in_msg->swap;
  swap->submarine_sender = submarine_sender;
  swap->submarine_receiver = submarine_receiver;
  // Swap amount S = B +P −C/2
  swap->amount = prev_backward_edge->balance + payment->amount -prev_channel->capacity/2;
  swap->start_time = tw_now(lp);
  swap->trigger_payment_id = payment->id;
  swap->state = REQUESTED;
  if (swap->amount <= 0){
    char lpstr[DEBUG_BUF_SIZE]; debug_lp("NODE", lp, lpstr);
    char objectstr[DEBUG_BUF_SIZE]; debug_submarine_swap(swap, objectstr);
    fprintf(node_out_file, "SS.c: %s starting swap with negative amount %s\n", lpstr, objectstr);
    printf("ERROR: %s starting swap with negative amount %s\n", lpstr, objectstr);
    exit(-1);
  }

  // Save the swap
  if (g_dbg_trace){
    char lpstr[DEBUG_BUF_SIZE]; debug_lp("NODE", lp, lpstr);
    char objectstr[DEBUG_BUF_SIZE]; debug_submarine_swap(swap, objectstr);
    fprintf(node_out_file, "SS.c: %s starting and saving %s\n", lpstr, objectstr);
  }
  node->submarine_swaps = array_insert(node->submarine_swaps, swap);

  // Forward the SWAP_REQUEST event
  tw_event *next_e = tw_event_new(prev_node->id, tw_rand_gamma(lp->rng, DELAY_GAMMA_DISTR_ALPHA, DELAY_GAMMA_DISTR_BETA), lp);
  struct message *next_msg = tw_event_data(next_e);
  next_msg->type = SWAP_REQUEST;
  serialize_submarine_swap(swap, next_msg->data);
  tw_event_send(next_e);
}

void submarine_swaps_on_forward_payment_rev(tw_lp *lp, struct message *in_msg){
  // Search for a submarine swap that was started by this forward event
  // Delete if the swap was started
  node_delete_swap(lp, in_msg->swap);
}

void submarine_swaps_on_swap_request(tw_lp *lp, struct message *in_msg){
  struct node *node = lp->cur_state;
  submarine_swap* swap = in_msg->swap;

  // Check requested swap
  if(swap->submarine_receiver != node->id) {
    exit(-1);
  }

  // Save swap
  node->submarine_swaps = array_insert(node->submarine_swaps, swap);

  // Send the prepare htlc
  struct blockchain_tx prepare_htlc_tx = {
    .type = PREPARE_HTLC,
    .sender = swap->submarine_receiver, // The prepare sender is the submarine receiver
    .receiver = swap->submarine_sender, // The prepare receiver is the submarine sender
    .amount = swap->amount,
    .start_time = tw_now(lp),
    .originator = node->id
  };
  tw_event *next_e = tw_event_new(blockchain_lp_gid, tw_rand_gamma(lp->rng, DELAY_GAMMA_DISTR_ALPHA, DELAY_GAMMA_DISTR_BETA), lp);
  struct message *next_msg = tw_event_data(next_e);
  next_msg->type = BC_TX_BROADCAST;
  serialize_blockchain_tx(&prepare_htlc_tx, next_msg->data);
  tw_event_send(next_e);
}

void submarine_swaps_on_swap_request_rev(tw_lp *lp, struct message *in_msg){
  node_delete_swap(lp, in_msg->swap);
}

void submarine_swaps_on_blockchain_tx(tw_lp *lp, struct blockchain_tx* tx){
  // Return if the blockchain transaction is not related to swaps
  if(tx->type!=PREPARE_HTLC && tx->type!=CLAIM_HTLC) return;

  struct node* node = lp->cur_state;
  struct submarine_swap* swap = node_find_swap_by_blockchain_tx(lp, tx);
  if (swap == NULL) return;

  // Else, here the swap has been found
  if(tx->type==PREPARE_HTLC && tx->sender==node->id){
    // Update swap state
    swap->state = L1_PREPARED;
  }
  else if (tx->type==PREPARE_HTLC && tx->receiver==node->id){
    // Update swap state
    swap->state = L1_PREPARED;
    // Create the payment
    struct payment* swap_to_forward = new_payment( swap->submarine_sender, swap->submarine_receiver, swap->amount, tw_now(lp), SUBMARINE_SWAP);
    // Forward the FINDPATH event to the current lp
    tw_event *next_e = tw_event_new(swap_to_forward->sender, 10, lp);
    struct message *next_msg = tw_event_data(next_e);
    next_msg->type = FINDPATH;
    serialize_payment(swap_to_forward, next_msg->data);
    tw_event_send(next_e);
  }
  else if (tx->type==CLAIM_HTLC){
    swap->state = L1_CLAIMED;
  }
}

void submarine_swaps_on_blockchain_tx_rev(tw_lp *lp, struct blockchain_tx* tx){
  // Return if the blockchain transaction is not related to swaps
  if(tx->type!=PREPARE_HTLC && tx->type!=CLAIM_HTLC) return;

  struct submarine_swap* swap = node_find_swap_by_blockchain_tx(lp, tx);
  if (swap == NULL) return;

  // Else, here the swap has been found
  if(tx->type==PREPARE_HTLC){
    swap->state = REQUESTED;
  }
  else if (tx->type==CLAIM_HTLC){
    swap->state = L1_PREPARED;
  }
}

void submarine_swaps_on_blockchain_tx_commit(tw_lp *lp, struct blockchain_tx* tx){
  // Return if the blockchain transaction is not related to swaps
  if(tx->type!=PREPARE_HTLC && tx->type!=CLAIM_HTLC) return;

  struct submarine_swap* swap = node_find_swap_by_blockchain_tx(lp, tx);
  if (swap==NULL){
    // Here the swap has not been found, fail with error
    char lpstr[DEBUG_BUF_SIZE]; debug_lp("NODE", lp, lpstr);
    char objectstr[DEBUG_BUF_SIZE]; debug_blockchain_tx(tx, objectstr);
    printf("ERROR: %s cannot find swap by committed blockchain tx %s\n", lpstr, objectstr);
    exit(-1);
  }
  // Else, here the swap has been found

  struct node *swap_receiver = array_get(network->nodes, swap->submarine_receiver);
  if(swap->state==L1_CLAIMED && tx->type==CLAIM_HTLC) {
    node_delete_swap(lp, swap);
  }
}

void submarine_swaps_on_receive_success(tw_lp *lp, struct payment* payment){
  // Return if the blockchain transaction is not related to swaps
  if(payment->type!=SUBMARINE_SWAP) return;

  struct node *node = lp->cur_state;
  struct submarine_swap* swap = node_find_swap_by_submarine_payment(lp, payment);

  // Claim HTLC
  struct blockchain_tx claim_htlc_tx = {
    .type = CLAIM_HTLC,
    .sender = swap->submarine_receiver, // The claim sender is the submarine receiver
    .receiver = swap->submarine_sender, // The claim receiver is the submarine sender
    .amount = swap->amount,
    .start_time = tw_now(lp),
    .originator = node->id
  };
  tw_event *next_e = tw_event_new(blockchain_lp_gid, tw_rand_gamma(lp->rng, DELAY_GAMMA_DISTR_ALPHA, DELAY_GAMMA_DISTR_BETA), lp);
  struct message *next_msg = tw_event_data(next_e);
  next_msg->type = BC_TX_BROADCAST;
  serialize_blockchain_tx(&claim_htlc_tx, next_msg->data);
  tw_event_send(next_e);
}

void submarine_swaps_on_receive_success_rev(tw_lp *lp, struct payment* payment){
  // Do nothing, since the only thing we did was generating the claim HTLC
}

void serialize_submarine_swap(submarine_swap* swap, char* serialized){
  if (!swap || !serialized) {
      return; // Invalid input or insufficient buffer size
  }
  char* current_pos = serialized + sizeof(size_t); // leave space for the size at the beginning

  // Serialize the swap
  memcpy(current_pos, &swap->submarine_sender, sizeof(swap->submarine_sender));
  current_pos += sizeof(swap->submarine_sender);

  memcpy(current_pos, &swap->submarine_receiver, sizeof(swap->submarine_receiver));
  current_pos += sizeof(swap->submarine_receiver);

  memcpy(current_pos, &swap->amount, sizeof(swap->amount));
  current_pos += sizeof(swap->amount);

  memcpy(current_pos, &swap->trigger_payment_id, sizeof(swap->trigger_payment_id));
  current_pos += sizeof(swap->trigger_payment_id);

  memcpy(current_pos, &swap->start_time, sizeof(swap->start_time));
  current_pos += sizeof(swap->start_time);

  memcpy(current_pos, &swap->state, sizeof(swap->state));
  current_pos += sizeof(swap->state);

  // Calculate the total size of the serialized string
  size_t serialized_size = current_pos - serialized;

  // Ensure that the serialized string doesn't exceed the maximum length
  if (serialized_size > MAX_SERIALIZED_LENGTH) {
      return; // Serialization exceeded the maximum length
  }

  // Add the serialized string size at the beginning
  memcpy(serialized, &serialized_size, sizeof(serialized_size));

  // Pad the remaining space with zeros
  size_t padding_size = MAX_SERIALIZED_LENGTH - serialized_size;
  if (padding_size > 0) {
      memset(serialized + serialized_size, 0, padding_size);
  }
}

submarine_swap* deserialize_submarine_swap(const char* serialized){
  submarine_swap* swap;
  size_t swap_size = 0;

  const char *current_pos = serialized;

  // Read the size of the serialized data
  memcpy(&swap_size, current_pos, sizeof(swap_size));
  current_pos += sizeof(swap_size);

  // Allocate memory for the tx structure
  swap = malloc(sizeof(struct submarine_swap));

  // Read tx fields
  memcpy(&swap->submarine_sender, current_pos, sizeof(swap->submarine_sender));
  current_pos += sizeof(swap->submarine_sender);

  memcpy(&swap->submarine_receiver, current_pos, sizeof(swap->submarine_receiver));
  current_pos += sizeof(swap->submarine_receiver);

  memcpy(&swap->amount, current_pos, sizeof(swap->amount));
  current_pos += sizeof(swap->amount);

  memcpy(&swap->trigger_payment_id, current_pos, sizeof(swap->trigger_payment_id));
  current_pos += sizeof(swap->trigger_payment_id);

  memcpy(&swap->start_time, current_pos, sizeof(swap->start_time));
  current_pos += sizeof(swap->start_time);

  memcpy(&swap->state, current_pos, sizeof(swap->state));
  current_pos += sizeof(swap->state);

  // Verify that the remaining evt_size is 0
  if (current_pos - serialized - swap_size != 0) {
    // Handle deserialization error (unexpected data size)
    printf("ERROR: swap unexpected data size during deserialization\n");
    exit(-1);
  }

  // Return the deserialized payment
  return swap;

}
