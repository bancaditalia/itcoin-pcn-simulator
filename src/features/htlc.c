#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <pthread.h>

#include "htlc.h"
#include "routing.h"
#include "network.h"

#include "../features/payments.h"

#include "../model/message.h"
#include "../model/pcn_node.h"
#include "../model/global.h"

#include "../utils/array.h"
#include "../utils/list.h"
#include "../utils/logging.h"
#include "../utils/utils.h"

/* Functions in this file simulate the HTLC mechanism for exchanging payments, as implemented in the Lightning Network.
   They are a (high-level) copy of functions in lnd-v0.9.1-beta (see files `routing/missioncontrol.go`, `htlcswitch/switch.go`, `htlcswitch/link.go`) */


/* AUXILIARY FUNCTIONS */

/* compute the fees to be paid to a hop for forwarding the payment */
uint64_t compute_fee(uint64_t amount_to_forward, struct policy policy) {
  uint64_t fee;
  fee = (policy.fee_proportional*amount_to_forward) / 1000000;
  return policy.fee_base + fee;
}

/* check whether there is sufficient balance in an edge for forwarding the payment; check also that the policies in the edge are respected */
unsigned int check_balance_and_policy(struct edge* edge, struct edge* prev_edge, struct route_hop* prev_hop, struct route_hop* next_hop) {
  uint64_t expected_fee;

  if(next_hop->amount_to_forward > edge->balance)
    return 0;

  if(next_hop->amount_to_forward < edge->policy.min_htlc){
    fprintf(stderr, "ERROR: policy.min_htlc not respected\n");
    exit(-1);
  }

  expected_fee = compute_fee(next_hop->amount_to_forward, edge->policy);
  if(prev_hop->amount_to_forward != next_hop->amount_to_forward + expected_fee){
    fprintf(stderr, "ERROR: policy.fee not respected\n");
    exit(-1);
  }

  if(prev_hop->timelock != next_hop->timelock + prev_edge->policy.timelock){
    fprintf(stderr, "ERROR: policy.timelock not respected\n");
    exit(-1);
  }

  return 1;
}

/* retrieve a hop from a payment route */
struct route_hop *get_route_hop(long node_id, struct array *route_hops, int is_sender) {
  struct route_hop *route_hop;
  long i, index = -1;

  for (i = 0; i < array_len(route_hops); i++) {
    route_hop = array_get(route_hops, i);
    if (is_sender && route_hop->from_node_id == node_id) {
      index = i;
      break;
    }
    if (!is_sender && route_hop->to_node_id == node_id) {
      index = i;
      break;
    }
  }

  if (index == -1)
    return NULL;

  return array_get(route_hops, index);
}


/* FUNCTIONS MANAGING NODE PAIR RESULTS */

/* set the result of a node pair as success: it means that a payment was successfully forwarded in an edge connecting the two nodes of the node pair.
 This information is used by the sender node to find a route that maximizes the possibilities of successfully sending a payment */
void set_node_pair_result_success(struct node* node, long from_node_id, long to_node_id, uint64_t success_amount, uint64_t success_time){
  struct node_pair_result* result;
  struct node_list_element *adj_list;

  adj_list = get_by_key(node->results, from_node_id, (int(*)(long, void*)) is_equal_node_list_element);
  if (adj_list == NULL){
    adj_list = malloc(sizeof(struct node_list_element));
    adj_list->from_node_id = from_node_id;
    adj_list->edges = NULL;
    node->results = push(node->results, adj_list);
  }

  result = get_by_key(adj_list->edges, to_node_id, (int(*)(long, void*)) is_equal_key_result);

  if(result == NULL){
    result = malloc(sizeof(struct node_pair_result));
    result->to_node_id = to_node_id;
    result->fail_time = 0;
    result->fail_amount = 0;
    result->success_time = 0;
    result->success_amount = 0;
    adj_list->edges = push(adj_list->edges, result);
  }

  result->success_time = success_time;
  if(success_amount > result->success_amount)
    result->success_amount = success_amount;
  if(result->fail_time != 0 && result->success_amount > result->fail_amount)
    result->fail_amount = success_amount + 1;
}

/* set the result of a node pair as success: it means that a payment failed when passing through  an edge connecting the two nodes of the node pair.
   This information is used by the sender node to find a route that maximizes the possibilities of successfully sending a payment */
void set_node_pair_result_fail(struct node* node, long from_node_id, long to_node_id, uint64_t fail_amount, uint64_t fail_time){
  struct node_pair_result* result;
  struct node_list_element *adj_list;

  adj_list = get_by_key(node->results, from_node_id, (int(*)(long, void*)) is_equal_node_list_element);
  if (adj_list == NULL){
    adj_list = malloc(sizeof(struct node_list_element));
    adj_list->from_node_id = from_node_id;
    adj_list->edges = NULL;
    node->results = push(node->results, adj_list);
  }

  result = get_by_key(adj_list->edges, to_node_id, (int(*)(long, void*)) is_equal_key_result);

  if(result != NULL)
    if(fail_amount > result->fail_amount && fail_time - result->fail_time < 60000)
      return;

  if(result == NULL){
    result = malloc(sizeof(struct node_pair_result));
    result->to_node_id = to_node_id;
    result->fail_time = 0;
    result->fail_amount = 0;
    result->success_time = 0;
    result->success_amount = 0;
    adj_list->edges = push(adj_list->edges, result);
  }

  result->fail_amount = fail_amount;
  result->fail_time = fail_time;
  if(fail_amount == 0)
    result->success_amount = 0;
  else if(fail_amount != 0 && fail_amount <= result->success_amount)
    result->success_amount = fail_amount - 1;
}

/* process a payment which succeeded */
void process_success_result(struct node* node, struct payment *payment, uint64_t current_time){
  struct route_hop* hop;
  int i;
  struct array* route_hops;
  route_hops = payment->route->route_hops;
  for(i=0; i<array_len(route_hops); i++){
    hop = array_get(route_hops, i);
    set_node_pair_result_success(node, hop->from_node_id, hop->to_node_id, hop->amount_to_forward, current_time);
  }
}

/* process a payment which failed (different processments depending on the error type) */
void process_fail_result(struct node* node, struct payment *payment, uint64_t current_time){
  struct route_hop* hop, *error_hop;
  int i;
  struct array* route_hops;

  error_hop = payment->error.hop;

  if(error_hop->from_node_id == payment->sender) //do nothing if the error was originated by the sender (see `processPaymentOutcomeSelf` in lnd)
    return;

  if(payment->error.type == OFFLINENODE) {
    set_node_pair_result_fail(node, error_hop->from_node_id, error_hop->to_node_id, 0, current_time);
    set_node_pair_result_fail(node, error_hop->to_node_id, error_hop->from_node_id, 0, current_time);
  }
  else if(payment->error.type == NOBALANCE) {
    route_hops = payment->route->route_hops;
    for(i=0; i<array_len(route_hops); i++){
      hop = array_get(route_hops, i);
      if(hop->edge_id == error_hop->edge_id) {
        set_node_pair_result_fail(node, hop->from_node_id, hop->to_node_id, hop->amount_to_forward, current_time);
        break;
      }
      set_node_pair_result_success(node, hop->from_node_id, hop->to_node_id, hop->amount_to_forward, current_time);
    }
  }
}

/*HTLC FUNCTIONS*/

/* find a path for a payment (a modified version of dijkstra is used: see `routing.c`) */
struct array * find_path(struct router_state *router_state, struct payment *payment, uint64_t current_time, struct network* network) {
  struct array *path;
  enum pathfind_error error;
  struct node* src, *dest;
  long sender_custodian, dest_custodian;
  char key[256];
  struct array* precomputed_hops;
  int precomputed_hops_len;
  struct path_hop *first_hop, *last_hop, *hop, *new_hop;
  struct edge* edge;

  ++(payment->attempts);

  if(is_expired_payment(payment, current_time)) {
    set_expired_payment(payment, current_time);
    return NULL;
  }
  src = array_get(network->nodes, payment->sender);
  dest = array_get(network->nodes, payment->receiver);
  sender_custodian = src->intermediary;
  dest_custodian = dest->intermediary;

  if (use_known_paths && payment->attempts==1 && sender_custodian != -1 && dest_custodian != -1){
    // Create the key "src-target"
    snprintf(key, sizeof(key), "%ld-%ld", sender_custodian, dest_custodian);
    precomputed_hops = hash_table_get(path_table, key);
    precomputed_hops_len = precomputed_hops != NULL ? array_len(precomputed_hops) : 0;
    path = array_initialize(precomputed_hops_len + 2);
    first_hop = (struct path_hop *)malloc(sizeof(struct path_hop));
    first_hop->sender = payment->sender;
    first_hop->receiver = sender_custodian;
    edge = array_get(src->open_edges, 0);
    first_hop->edge = edge->id;
    path = array_insert(path, first_hop);
    for(int i=0; i<precomputed_hops_len; i++){
      hop = array_get(precomputed_hops,i);
      new_hop = (struct path_hop *)malloc(sizeof(struct path_hop));
      new_hop->edge = hop->edge;
      new_hop->sender = hop->sender;
      new_hop->receiver = hop->receiver;
      path = array_insert(path, new_hop);
    }
    last_hop = (struct path_hop *)malloc(sizeof(struct path_hop));
    last_hop->sender = dest_custodian;
    last_hop->receiver = payment->receiver;
    edge =  array_get(dest->open_edges, 0);
    last_hop->edge = edge->counter_edge_id;
    path = array_insert(path, last_hop);
  }
  else
    path = dijkstra(router_state, payment->sender, payment->receiver, payment->last_hop_id, payment->amount, network, current_time, &error);

  if (path != NULL) {
    return path;
  }

  // Payment has failed because the path cant be found
  if (payment->error.type == NOERROR){
    payment->error.type = NOCAPACITY;
    payment->error.time = current_time;
    payment->error.hop = NULL;
  }
  payment->end_time = current_time;
  return NULL;
}

/* send an HTLC for the payment (behavior of the payment sender) */
int send_payment(tw_lp *lp, struct payment* payment) {
  // Get the node
  struct node* node = lp->cur_state;

  // Get the route
  struct route* route = payment->route;
  struct route_hop* first_route_hop = array_get(route->route_hops, 0);
  struct edge* next_edge = array_get(network->edges, first_route_hop->edge_id);
  if(!is_present(next_edge->id, node->open_edges)) {
    printf("ERROR (send_payment): edge %ld is not an edge of node %ld \n", next_edge->id, node->id);
    exit(-1);
  }

  /* simulate the case that the next node in the route is offline */
  int is_next_node_offline = 0;
  if(is_next_node_offline){
    payment->offline_node_count += 1;
    payment->error.type = OFFLINENODE;
    payment->error.hop = first_route_hop;
    // Generate RECEIVEFAIL
    tw_event *receive_fail_e = tw_event_new(lp->gid, OFFLINELATENCY, lp);
    struct message *receive_fail_msg = tw_event_data(receive_fail_e);
    receive_fail_msg->type = RECEIVEFAIL;
    serialize_payment(payment, receive_fail_msg->data);
    tw_event_send(receive_fail_e);
    return 0;
  }

  if(first_route_hop->amount_to_forward > next_edge->balance) {
    payment->error.type = NOBALANCE;
    payment->error.time = tw_now(lp);
    payment->error.hop = first_route_hop;
    payment->no_balance_count += 1;
    // Generate RECEIVEFAIL
    tw_event* next_e = tw_event_new(lp->gid, 10, lp);
    struct message* next_msg = tw_event_data(next_e);
    next_msg->type = RECEIVEFAIL;
    serialize_payment(payment, next_msg->data);
    tw_event_send(next_e);
    return 0;
  }

  // State updates
  next_edge->balance -= first_route_hop->amount_to_forward;
  next_edge->tot_flows += 1;

  // Generate RECEIVEPAYMENT or FORWARDPAYMENT
  unsigned int rng_calls = 0;
  tw_event *next_e = tw_event_new(first_route_hop->to_node_id, tw_rand_gamma(lp->rng, DELAY_GAMMA_DISTR_ALPHA, DELAY_GAMMA_DISTR_BETA), lp);
  struct message *next_msg = tw_event_data(next_e);
  next_msg->type = first_route_hop->to_node_id == payment->receiver ? RECEIVEPAYMENT : FORWARDPAYMENT;
  serialize_payment(payment, next_msg->data);
  tw_event_send(next_e);
  return 1;
}

/* forward an HTLC for the payment (behavior of an intermediate hop node in a route) */
int forward_payment(tw_lp *lp, struct payment* payment) {
  struct node *node = lp->cur_state;

  struct route* route = payment->route;
  struct route_hop* next_route_hop=get_route_hop(node->id, route->route_hops, 1);
  struct edge* next_edge = array_get(network->edges, next_route_hop->edge_id);
  struct node* next_node = array_get(network->nodes, next_edge->to_node_id);
  struct route_hop* previous_route_hop = get_route_hop(node->id, route->route_hops, 0);
  struct edge* prev_edge = array_get(network->edges,previous_route_hop->edge_id);
  struct edge* prev_backward_edge = array_get(network->edges, prev_edge->counter_edge_id);
  struct channel* prev_channel = array_get(network->channels, prev_edge->channel_id);
  struct node* prev_node = array_get(network->nodes, prev_edge->from_node_id);

  if(!is_present(next_route_hop->edge_id, node->open_edges)) {
    printf("ERROR (forward_payment): edge %ld is not an edge of node %ld \n", next_route_hop->edge_id, node->id);
    exit(-1);
  }

  // Init the rng calls counter
  unsigned int rng_calls = 0;

  /* simulate the case that the next node in the route is offline */
  int is_next_node_offline = 0;
  if(is_next_node_offline && !(next_route_hop->to_node_id == payment->receiver)){ //assume that the receiver node is always online
    payment->offline_node_count += 1;
    payment->error.type = OFFLINENODE;
    payment->error.hop = next_route_hop;
    int prev_node_id = previous_route_hop->from_node_id;
    // Generate RECEIVEFAIL or FORWARDFAIL
    tw_event *receive_fail_e = tw_event_new(prev_node_id, tw_rand_gamma(lp->rng, DELAY_GAMMA_DISTR_ALPHA, DELAY_GAMMA_DISTR_BETA) + OFFLINELATENCY, lp);
    struct message *receive_fail_msg = tw_event_data(receive_fail_e);
    receive_fail_msg->type = prev_node_id == payment->sender ? RECEIVEFAIL : FORWARDFAIL;
    serialize_payment(payment, receive_fail_msg->data);
    tw_event_send(receive_fail_e);
    return 0;
  }

  // Check forwarding conditions
  unsigned int can_send_htlc = check_balance_and_policy(next_edge, prev_edge, previous_route_hop, next_route_hop);

  // Check the waterfall conditions
  unsigned int await_waterfall =
    waterfall_enabled &&
    !can_send_htlc &&
    payment->type == TX &&
    node->type == INTERMEDIARY &&
    next_node->id == payment->receiver &&
    (next_node->type == END_USER || next_node->type == MERCHANT) &&
    tw_now(lp) < payment->start_time + payments_expire_after_ms;

  if (await_waterfall){
    // We use the error type to check wether the notifypayment has already been sent. TODO incude a proper field.
    if (payment->error.type == NOERROR){
      payment->error.type = NOBALANCE;
      tw_event* notify_evt = tw_event_new(payment->receiver, tw_rand_gamma(lp->rng, DELAY_GAMMA_DISTR_ALPHA, DELAY_GAMMA_DISTR_BETA), lp);
      struct message* notify_msg = tw_event_data(notify_evt);
      notify_msg->type = NOTIFYPAYMENT;
      serialize_payment(payment, notify_msg->data);
      tw_event_send(notify_evt);
    }

    // Retry to forward in a few sec
    tw_event *next_e = tw_event_new(node->id, tw_rand_gamma(lp->rng, DELAY_GAMMA_DISTR_ALPHA, DELAY_GAMMA_DISTR_BETA), lp);
    struct message *next_msg = tw_event_data(next_e);
    next_msg->type = FORWARDPAYMENT;
    serialize_payment(payment, next_msg->data);
    tw_event_send(next_e);
    return 0;
  }
  else if(!can_send_htlc){
    payment->error.type = NOBALANCE;
    payment->error.hop = next_route_hop;
    payment->error.time = tw_now(lp);
    payment->no_balance_count += 1;
    long prev_node_id = previous_route_hop->from_node_id;
    // Generate RECEIVEFAIL or FORWARDFAIL
    tw_event *next_e = tw_event_new(prev_node_id, tw_rand_gamma(lp->rng, DELAY_GAMMA_DISTR_ALPHA, DELAY_GAMMA_DISTR_BETA), lp);
    struct message *next_msg = tw_event_data(next_e);
    next_msg->type = prev_node_id == payment->sender ? RECEIVEFAIL : FORWARDFAIL;
    serialize_payment(payment, next_msg->data);
    tw_event_send(next_e);
    return 0;
  }

  // State updates
  next_edge->balance -= next_route_hop->amount_to_forward;
  next_edge->tot_flows += 1;

  // Generate RECEIVEPAYMENT or FORWARDPAYMENT
  tw_event *next_e = tw_event_new(next_route_hop->to_node_id, tw_rand_gamma(lp->rng, DELAY_GAMMA_DISTR_ALPHA, DELAY_GAMMA_DISTR_BETA), lp);
  struct message *next_msg = tw_event_data(next_e);
  next_msg->type = next_route_hop->to_node_id == payment->receiver ? RECEIVEPAYMENT : FORWARDPAYMENT;
  serialize_payment(payment, next_msg->data);
  tw_event_send(next_e);
  return 1;
}

/* receive a payment (behavior of the payment receiver node) */
void receive_payment(tw_lp *lp, struct payment* payment){
  long  prev_node_id;
  struct route* route;
  struct route_hop* last_route_hop;
  struct edge* forward_edge,*backward_edge;
  struct node* node = lp->cur_state;

  route = payment->route;

  last_route_hop = array_get(route->route_hops, array_len(route->route_hops) - 1);
  forward_edge = array_get(network->edges, last_route_hop->edge_id);
  backward_edge = array_get(network->edges, forward_edge->counter_edge_id);

  if(!is_present(backward_edge->id, node->open_edges)) {
    printf("ERROR (receive_payment): edge %ld is not an edge of node %ld \n", backward_edge->id, node->id);
    exit(-1);
  }

  backward_edge->balance += last_route_hop->amount_to_forward;

  payment->is_success = 1;

  prev_node_id = last_route_hop->from_node_id;
  // Generate RECEIVESUCCESS or FORWARDSUCCESS
  unsigned int rng_calls = 0;
  tw_event *next_e = tw_event_new(prev_node_id, tw_rand_gamma(lp->rng, DELAY_GAMMA_DISTR_ALPHA, DELAY_GAMMA_DISTR_BETA), lp);
  struct message *next_msg = tw_event_data(next_e);
  next_msg->type = prev_node_id == payment->sender ? RECEIVESUCCESS : FORWARDSUCCESS;
  serialize_payment(payment, next_msg->data);
  tw_event_send(next_e);

  if (payment->type == WITHDRAWAL){
    if (payment->receiver != node->id){
      printf("model has RECEIVE_PAYMENT event with WITHDRAWAL, but payment receiver is not node id, this should not happen\n");
      exit(-1);
    }
    // Search for the awaiting payment
    if(node->rw_awaiting_payment != NULL && node->rw_withdrawal_id == payment->id){
      // The awaiting payment has been found, create the FINDPATH
      tw_event *find_path_e = tw_event_new(node->rw_awaiting_payment->sender, 10, lp);
      struct message *find_path_msg = tw_event_data(find_path_e);
      find_path_msg->type = FINDPATH;
      serialize_payment(node->rw_awaiting_payment, find_path_msg->data);
      tw_event_send(find_path_e);
    }
  }
}

/* forward an HTLC success back to the payment sender (behavior of a intermediate hop node in the route) */
void forward_success(tw_lp *lp, struct payment* payment) {
  struct route_hop* prev_hop;
  struct edge* forward_edge, * backward_edge;
  long prev_node_id;
  struct node* node = lp->cur_state;

  prev_hop = get_route_hop(lp->gid, payment->route->route_hops, 0);
  forward_edge = array_get(network->edges, prev_hop->edge_id);
  backward_edge = array_get(network->edges, forward_edge->counter_edge_id);

  if(!is_present(backward_edge->id, node->open_edges)) {
    printf("ERROR (forward_success): edge %ld is not an edge of node %ld \n", backward_edge->id, node->id);
    exit(-1);
  }

  backward_edge->balance += prev_hop->amount_to_forward;

  prev_node_id = prev_hop->from_node_id;
  // Generate RECEIVESUCCESS or FORWARDSUCCESS
  unsigned int rng_calls = 0;
  tw_event *next_e = tw_event_new(prev_node_id, tw_rand_gamma(lp->rng, DELAY_GAMMA_DISTR_ALPHA, DELAY_GAMMA_DISTR_BETA), lp);
  struct message *next_msg = tw_event_data(next_e);
  next_msg->type = prev_node_id == payment->sender ? RECEIVESUCCESS : FORWARDSUCCESS;
  serialize_payment(payment, next_msg->data);
  tw_event_send(next_e);
}

/* receive an HTLC success (behavior of the payment sender node) */
void receive_success(tw_lp *lp, struct payment* payment){
  payment->end_time = tw_now(lp);
}

/* forward an HTLC fail back to the payment sender (behavior of a intermediate hop node in the route) */
void forward_fail(tw_lp *lp, struct payment* payment) {
  struct route_hop* next_hop, *prev_hop;
  struct edge* next_edge;
  long prev_node_id;

  struct node* node = lp->cur_state;
  next_hop = get_route_hop(lp->gid, payment->route->route_hops, 1);
  next_edge = array_get(network->edges, next_hop->edge_id);

  if(!is_present(next_edge->id, node->open_edges)) {
    printf("ERROR (forward_fail): edge %ld is not an edge of node %ld \n", next_edge->id, node->id);
    exit(-1);
  }

  /* since the payment failed, the balance must be brought back to the state before the payment occurred */
  next_edge->balance += next_hop->amount_to_forward;

  prev_hop = get_route_hop(lp->gid, payment->route->route_hops, 0);
  prev_node_id = prev_hop->from_node_id;

  // Generate RECEIVEFAIL or FORWARDFAIL
  unsigned int rng_calls = 0;
  tw_event *next_e = tw_event_new(prev_node_id, tw_rand_gamma(lp->rng, DELAY_GAMMA_DISTR_ALPHA, DELAY_GAMMA_DISTR_BETA), lp);
  struct message *next_msg = tw_event_data(next_e);
  next_msg->type = prev_node_id == payment->sender ? RECEIVEFAIL : FORWARDFAIL;
  serialize_payment(payment, next_msg->data);
  tw_event_send(next_e);
}

/* receive an HTLC fail (behavior of the payment sender node) */
void receive_fail(tw_lp *lp, struct payment* payment) {
  struct route_hop* first_hop, *error_hop;
  struct edge* next_edge;
  struct event* next_event;
  struct node* node = lp->cur_state;

  error_hop = payment->error.hop;
  if(error_hop->from_node_id != payment->sender){ // if the error occurred in the first hop, the balance hasn't to be updated, since it was not decreased
    first_hop = array_get(payment->route->route_hops, 0);
    next_edge = array_get(network->edges, first_hop->edge_id);
    if(!is_present(next_edge->id, node->open_edges)) {
      printf("ERROR (receive_fail): edge %ld is not an edge of node %ld \n", next_edge->id, node->id);
      exit(-1);
    }
    next_edge->balance += first_hop->amount_to_forward;
  }

  // Generate FINDPATH
  tw_event *next_e = tw_event_new(payment->sender, 10, lp);
  struct message *next_msg = tw_event_data(next_e);
  next_msg->type = FINDPATH;
  serialize_payment(payment, next_msg->data);
  tw_event_send(next_e);
}

void notify_payment(tw_lp *lp, struct payment* payment) {
  struct node* node = lp->cur_state;
  if(node->id != payment->receiver) {
    printf("ERROR (notify_payment): node id %ld and payment receiver %ld are not the same\n", node->id, payment->receiver);
    exit(-1);
  }

  // Init rng counter
  unsigned int rng_calls = 0;

  // Deposit amount D = B +P −C
  long node_wcap = get_node_wallet_cap(network, node);
  long node_balance = get_node_available_balance(node);
  long amount_d = node_balance + payment->amount - node_wcap;

  // Deposit at least node_wcap/3
  amount_d = amount_d > node_wcap/3 ? amount_d : node_wcap/3;
  // Create deposit
  struct payment* deposit_to_forward = new_payment( node->id, node->intermediary, amount_d, tw_now(lp), DEPOSIT);
  // Forward the FINDPATH event
  // Here we would like to simulate a RTT between the user and its custodian, to ask and receive for a deposit invoice (200 + 2*RAND), plus the time to create the findpath event (10)
  tw_event *next_e = tw_event_new(deposit_to_forward->sender, 10 + 2*tw_rand_gamma(lp->rng, DELAY_GAMMA_DISTR_ALPHA, DELAY_GAMMA_DISTR_BETA), lp);
  struct message *next_msg = tw_event_data(next_e);
  next_msg->type = FINDPATH;
  serialize_payment(deposit_to_forward, next_msg->data);
  tw_event_send(next_e);
  free_payment(deposit_to_forward);
}


void rev_send_payment(tw_lp *lp, struct payment* payment) {
  struct node* node = lp->cur_state;
  struct route* route = payment->route;
  struct route_hop* first_route_hop = array_get(route->route_hops, 0);
  struct edge* next_edge = array_get(network->edges, first_route_hop->edge_id);

  // Revert state updates
  next_edge->balance += first_route_hop->amount_to_forward;
  next_edge->tot_flows -= 1;
}

void rev_forward_payment(tw_lp *lp, struct payment* payment) {
  struct route* route = payment->route;
  struct node* node = lp->cur_state;

  struct route_hop* next_route_hop=get_route_hop(node->id, route->route_hops, 1);
  struct edge* next_edge = array_get(network->edges, next_route_hop->edge_id);

  next_edge->balance += next_route_hop->amount_to_forward;
  next_edge->tot_flows -= 1;
}

void rev_receive_payment(tw_lp *lp, struct payment* payment) {
  struct route* route;
  struct route_hop* last_route_hop;
  struct edge* forward_edge, *backward_edge;
  struct node* node;

  route = payment->route;

  node = lp->cur_state;

  last_route_hop = array_get(route->route_hops, array_len(route->route_hops) - 1);
  forward_edge = array_get(network->edges, last_route_hop->edge_id);
  backward_edge = array_get(network->edges, forward_edge->counter_edge_id);
  backward_edge->balance -= last_route_hop->amount_to_forward;
}

void rev_forward_success(tw_lp *lp, struct payment* payment) {
  struct route_hop* prev_hop;
  struct edge* forward_edge, * backward_edge;

  prev_hop = get_route_hop(lp->gid, payment->route->route_hops, 0);
  forward_edge = array_get(network->edges, prev_hop->edge_id);
  backward_edge = array_get(network->edges, forward_edge->counter_edge_id);

  backward_edge->balance -= prev_hop->amount_to_forward;
}
void rev_receive_success(tw_lp *lp, struct payment* payment){
  payment->end_time = 0;
}
void rev_forward_fail(tw_lp *lp, struct payment* payment) {
  struct route_hop* next_hop;
  struct edge* next_edge;

  next_hop = get_route_hop(lp->gid, payment->route->route_hops, 1);
  next_edge = array_get(network->edges, next_hop->edge_id);

  next_edge->balance -= next_hop->amount_to_forward;
}

void rev_receive_fail(tw_lp *lp, struct payment* payment) {
  struct route_hop* first_hop, *error_hop;
  struct edge* next_edge;

  error_hop = payment->error.hop;
  if(error_hop->from_node_id != payment->sender){
    first_hop = array_get(payment->route->route_hops, 0);
    next_edge = array_get(network->edges, first_hop->edge_id);
    next_edge->balance -= first_hop->amount_to_forward;
  }
}

void rev_notify_payment(tw_lp *lp, struct payment* payment) {
}
